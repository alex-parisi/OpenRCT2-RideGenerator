"""
Stall sprite rendering.

Shops (Shop.cpp) paint `base_image_id + direction` with a {0,0} paint offset,
so a stall renders like large scenery: 4 cardinal views, each anchored at the
tile's per-direction reference corner. Facilities (Facility.cpp) paint
`base_image_id + ((direction + 2) & 3)`, splitting directions 1/2 into a
doorway sprite plus a building-body overlay so peeps sort into the doorway.
"""

from collections.abc import Callable

import numpy as np
from openrct2_object_common.export import ProgressFn
from openrct2_object_common.sprite_render import (
    IDENTITY3,
    add_split_ghost,
    center_in_box,
    corner_anchors,
    render_corner_anchored_view,
    trim,
)
from openrct2_x7_renderer.constants import TILE_SIZE, MeshFlag
from openrct2_x7_renderer.geometry import combine_model_world, split_mesh_by_ghost
from openrct2_x7_renderer.mesh import Mesh
from openrct2_x7_renderer.ray_trace import VIEWS, Context
from openrct2_x7_renderer.types import IndexedImage, Model

from .constants import (
    BUILDING_VIEW_SPRITES,
    FACILITY_VIEW_SPRITES,
    FLAT_RIDE_SPECS,
    HAUNTED_HOUSE_OVERLAY_SPRITES,
    PREVIEW_BOX,
    SHOP_VIEW_SPRITES,
    STALL_TYPES,
    StallKind,
)


def count_stall_sprites(stall_type: str) -> int:
    """View sprites for a stall type (the 3 preview slots are extra;
    haunted house ghost overlays count as view sprites here)."""
    if STALL_TYPES[stall_type] is StallKind.FACILITY:
        return FACILITY_VIEW_SPRITES
    if STALL_TYPES[stall_type] is StallKind.BUILDING:
        extra = HAUNTED_HOUSE_OVERLAY_SPRITES if stall_type == "haunted_house" else 0
        return BUILDING_VIEW_SPRITES + extra
    if STALL_TYPES[stall_type] is StallKind.FLAT_RIDE:
        spec = FLAT_RIDE_SPECS[stall_type]
        return spec.structure_sprites + spec.rider_slots
    return SHOP_VIEW_SPRITES


def _render_direction(
    context: Context, mesh: Mesh, direction: int, units_per_tile: float
) -> IndexedImage:
    """Render `mesh` for one view direction, corner-anchored. A stall anchors at
    the tile's reference corner like large scenery, so this is the shared
    corner-anchor primitive (see openrct2_object_common)."""
    return render_corner_anchored_view(
        context, mesh, direction, units_per_tile=units_per_tile
    )


def render_shop(
    context: Context,
    combined: Mesh,
    units_per_tile: float = TILE_SIZE,
    progress: ProgressFn | None = None,
) -> list[IndexedImage]:
    """Render a shop sprite set: image k is the building at view direction k."""
    images = []
    for d in range(SHOP_VIEW_SPRITES):
        images.append(_render_direction(context, combined, d, units_per_tile))
        if progress is not None:
            progress(d + 1, SHOP_VIEW_SPRITES)
    return images


def render_building(
    context: Context,
    combined: Mesh,
    stall_type: str,
    units_per_tile: float = TILE_SIZE,
    progress: ProgressFn | None = None,
) -> list[IndexedImage]:
    """Render a 3x3 building sprite set: image k is the whole building at view
    direction k, anchored at the centre tile's reference corner (the mesh is
    authored centred on the middle tile). Haunted house gets 72 blank ghost
    overlays appended (base + 3 + direction * 18 + frame) so the engine never
    paints a stray image while the ride is operating."""
    images = []
    for d in range(BUILDING_VIEW_SPRITES):
        images.append(_render_direction(context, combined, d, units_per_tile))
        if progress is not None:
            progress(d + 1, BUILDING_VIEW_SPRITES)
    if stall_type == "haunted_house":
        images += [IndexedImage.blank(1, 1)] * HAUNTED_HOUSE_OVERLAY_SPRITES
    return images


def _render_pose(context: Context, combined: Mesh, direction: int) -> IndexedImage:
    """One baked pose rendered from a view direction (blank if it has no geometry).

    OpenRCT2's flat-ride structure painter draws the sprite at the tile's
    per-direction reference CORNER (paint offset ``{0,0}`` of the centre tile, e.g.
    ``Twist.cpp`` ``paint_twist_structure``'s ``{xOffset, yOffset, height}``), not
    the tile centre -- the same corner anchoring as stalls and large scenery. So a
    pose is corner-anchored too; centre-anchoring would sit the whole structure
    half a tile toward the back corner."""
    return render_corner_anchored_view(context, combined, direction)


def _render_masked_pose(
    context: Context, drawn: Mesh, occluder: Mesh, direction: int
) -> IndexedImage:
    """Render ``drawn`` corner-anchored under ``direction`` with ``occluder``
    present only as a depth mask (``MeshFlag.MASK``): the occluder blocks rays but
    is not itself drawn, so ``drawn``'s pixels hidden behind it are clipped from
    the sprite.

    This is the rider-occlusion trick the vehicle generator uses for peeps behind a
    car (``placement.add_model_to_scene`` with ``mask=1``), applied to a flat
    ride's rider ring: the engine paints rider overlays on top of the structure
    with no depth test, so pre-clipping each rider against the structure is the only
    way far-side riders read as occluded by the canopy. Anchoring mirrors
    :func:`render_corner_anchored_view` (centre tile, corner-anchored)."""
    if drawn.faces.shape[0] == 0:
        return IndexedImage.blank(1, 1)
    ox, oz = corner_anchors(TILE_SIZE)[direction]
    translation = np.array([-ox, 0.0, -oz], dtype=np.float64)
    with context.begin_render() as scene:
        # The occluder first, flagged as a mask (contributes depth, not drawn); the
        # ghost split keeps any see-through structure materials see-through.
        for sub_mesh, mask in split_mesh_by_ghost(occluder, int(MeshFlag.MASK)):
            scene.add_model(sub_mesh, IDENTITY3, translation, mask)
        add_split_ghost(scene, drawn, translation)
        with scene.finalize() as ready:
            return ready.render_view(VIEWS[direction])


def _structure_pose_for_rider(frames: int) -> Callable[[int], int]:
    """Map a rider-ring frame to the structure pose that occludes it. For the
    twist the rider offsets are multiples of the structure period, so rider frame
    ``f`` is shown with structure pose ``f % frames``."""

    def index(f: int) -> int:
        return f % frames

    return index


def _render_ring(
    context: Context,
    meshes: list[Mesh],
    model: Model,
    directions: int,
    frames: int,
    direction_minor: bool,
    blank_sub_slots: int = 0,
    progress: ProgressFn | None = None,
    progress_done: int = 0,
    progress_total: int = 0,
    sub_models: list[Model] | None = None,
    occluder_posed: list[Mesh] | None = None,
    occluder_for_frame: Callable[[int], int] | None = None,
) -> list[IndexedImage]:
    """Render one ring of a flat ride: a multi-frame ``model`` baked pose by pose
    and rendered from each view direction, in the engine's image order.

    When ``occluder_posed`` and ``occluder_for_frame`` are given, each pose is
    rendered with ``occluder_posed[occluder_for_frame(f)]`` present as a depth mask
    (see :func:`_render_masked_pose`) -- the rider ring pre-clipped against the
    structure so far-side riders read as occluded rather than painted on top.

    ``direction_minor`` selects that order: direction-major (``image = direction *
    frames + frame``, the ferris/carousel layout) or direction-minor (``image =
    frame * directions + direction``, ``Enterprise.cpp`` reads ``base +
    (animationFrame << 2) + direction``). Each rendered image is trailed by
    ``blank_sub_slots`` interleaved slots (the swinging ship's per-bench riders):
    blank, or -- when ``sub_models`` is given (one model per sub-slot) -- that
    bench row's rider posed at the same frame and view. Used for both the structure
    ring and the trailing rider ring."""
    # Each pose's baked mesh is the same across directions, so bake once per pose.
    posed = [combine_model_world(meshes, model, frame=f) for f in range(frames)]
    sub_posed = None
    if sub_models:
        sub_posed = [
            [combine_model_world(meshes, sm, frame=f) for f in range(frames)]
            for sm in sub_models
        ]
    if direction_minor:
        order = [(d, f) for f in range(frames) for d in range(directions)]
    else:
        order = [(d, f) for d in range(directions) for f in range(frames)]
    images: list[IndexedImage] = []
    total = progress_total or (len(order) * (1 + blank_sub_slots))
    for d, f in order:
        if occluder_posed is not None and occluder_for_frame is not None:
            images.append(
                _render_masked_pose(context, posed[f], occluder_posed[occluder_for_frame(f)], d)
            )
        else:
            images.append(_render_pose(context, posed[f], d))
        for sub in range(blank_sub_slots):
            if sub_posed is not None and sub < len(sub_posed):
                images.append(_render_pose(context, sub_posed[sub][f], d))
            else:
                images.append(IndexedImage.blank(1, 1))
        if progress is not None:
            progress(progress_done + len(images), total)
    return images


def render_flat_ride(
    context: Context,
    meshes: list[Mesh],
    model: Model,
    rider_model: Model,
    stall_type: str,
    progress: ProgressFn | None = None,
    rider_sub_models: list[Model] | None = None,
) -> list[IndexedImage]:
    """Render an animated flat ride sprite set: the structure ring (one image per
    view direction and animation pose), followed by the rider ring.

    The structure is a vehicle sprite anchored at the centre tile's per-direction
    reference corner (see :func:`_render_pose`). Each pose bakes one frame of the
    multi-frame ``model`` (the Blender-authored spin); the camera direction is the
    world rotation ``VIEWS[d]``. The merry-go-round is rotationally
    symmetric, so it stores a single direction (the engine folds the camera rotation
    out and reuses the ring); the ferris wheel is not, so it stores all four
    (``FerrisWheel.cpp`` reads ``base + direction * 8 + frame``).

    Riders come in two shapes. Most rides trail a second ring -- a seated rider-pair
    posed once per rider-strip frame (``rider_model``). The swinging ship instead
    interleaves its riders into the sub-slots after each ship sprite (one
    ``rider_sub_models`` model per bench row). Either may be absent, in which case
    those slots are emitted blank, like the haunted house's ghosts, so the engine
    never paints a stray peep image.

    When ``spec.rider_masked_by_structure`` is set (the twist), the rider ring is
    rendered with the structure as a depth-mask occluder so far-side riders are
    clipped behind the canopy instead of painted over it. The structure pose that
    occludes rider frame ``f`` is ``f % spec.frames`` -- the twist's rider offsets
    are multiples of the structure period, so a rider at phase ``f`` is always shown
    with the structure in that pose, and the ride's 9-fold symmetry makes its
    geometry exact at the rider's angle."""
    spec = FLAT_RIDE_SPECS[stall_type]
    rider_sub_models = rider_sub_models or []
    structure_total = spec.structure_sprites
    render_riders = spec.has_rider_ring and bool(rider_model.meshes)
    render_sub_riders = spec.has_rider_sub_slots and any(m.meshes for m in rider_sub_models)
    sub_models = rider_sub_models if render_sub_riders else None
    # Progress counts the images actually rendered: the structure ring always (its
    # sub-slots rendered only when riders fill them), the trailing rider ring only
    # when the object carries rider geometry (else those slots are blanks).
    total = structure_total + (spec.rider_slots if render_riders else 0)
    images = _render_ring(
        context, meshes, model, spec.directions, spec.frames, spec.direction_minor,
        spec.blank_sub_slots, progress, progress_done=0, progress_total=total,
        sub_models=sub_models,
    )
    if render_riders:
        occluder_posed: list[Mesh] | None = None
        occluder_index: Callable[[int], int] | None = None
        if spec.rider_masked_by_structure:
            occluder_posed = [
                combine_model_world(meshes, model, frame=f) for f in range(spec.frames)
            ]
            occluder_index = _structure_pose_for_rider(spec.frames)
        images += _render_ring(
            context, meshes, rider_model, spec.rider_directions, spec.rider_frames,
            spec.rider_direction_minor, 0, progress,
            progress_done=structure_total, progress_total=total,
            occluder_posed=occluder_posed, occluder_for_frame=occluder_index,
        )
    else:
        images += [IndexedImage.blank(1, 1)] * spec.rider_slots
    return images


# Cropping transparent borders (preserving the draw anchor) is shared with
# every other object kind (see openrct2_object_common).
_trim = trim


def split_door_strip(full: IndexedImage, door: IndexedImage) -> tuple[IndexedImage, IndexedImage]:
    """Cut a full-building render into (doorway strip, body) at the door-only
    render's opaque screen-x extent, like the vanilla facility sprites.

    The body overlay's top-slab bound box sorts above the door sprite, so the
    engine paints the body on top; cutting both sprites from one render along
    pixel columns makes them tile back together exactly in either paint order.
    Returns (blank, full) when the door render has no opaque pixels inside the
    building's columns."""
    cols = np.flatnonzero(door.pixels.any(axis=0))
    if cols.size == 0:
        return IndexedImage.blank(1, 1), full
    lo = max(door.x_offset + int(cols[0]) - full.x_offset, 0)
    hi = min(door.x_offset + int(cols[-1]) + 1 - full.x_offset, full.width)
    if lo >= hi:
        return IndexedImage.blank(1, 1), full
    strip = np.zeros_like(full.pixels)
    strip[:, lo:hi] = full.pixels[:, lo:hi]
    body = full.pixels.copy()
    body[:, lo:hi] = 0
    door_img = IndexedImage(
        width=full.width, height=full.height,
        x_offset=full.x_offset, y_offset=full.y_offset, pixels=strip,
    )
    body_img = IndexedImage(
        width=full.width, height=full.height,
        x_offset=full.x_offset, y_offset=full.y_offset, pixels=body,
    )
    return _trim(door_img), _trim(body_img)


# The doorway must face the camera at view directions 1 and 2 (where
# Facility.cpp paints the door sprite and the body overlay) and face away at
# 0 and 3. Under this renderer's dimetric camera that is the tile's +X edge,
# so a facility is authored with its door facing OBJ +X.
def render_facility(
    context: Context,
    combined: Mesh,
    door: Mesh | None = None,
    units_per_tile: float = TILE_SIZE,
    progress: ProgressFn | None = None,
) -> list[IndexedImage]:
    """Render a facility sprite set in Facility.cpp's image order.

    Image k serves view direction (k + 2) & 3: k=0/3 are the doorway strips
    for directions 2/1, k=1/2 the full building for directions 3/0, and k=4/5
    the building-body remainders for directions 2/1. `door` is the marked
    doorway geometry; it is rendered only to locate the strip boundary, the
    sprite pixels always come from the full-building render (`split_door_strip`).
    Without `door` the full building fills the directional slots and the
    overlays are blank."""
    if door is not None and door.faces.shape[0] == 0:
        door = None
    passes = [(combined, 2), (combined, 3), (combined, 0), (combined, 1)]
    if door is not None:
        passes += [(door, 2), (door, 1)]
    rendered = []
    for k, (mesh, d) in enumerate(passes):
        rendered.append(_render_direction(context, mesh, d, units_per_tile))
        if progress is not None:
            progress(k + 1, len(passes))
    full2, full3, full0, full1 = rendered[:4]
    if door is None:
        return [full2, full3, full0, full1, IndexedImage.blank(1, 1), IndexedImage.blank(1, 1)]
    door2, body2 = split_door_strip(full2, rendered[4])
    door1, body1 = split_door_strip(full1, rendered[5])
    return [door2, full3, full0, door1, body2, body1]


def center_preview(img: IndexedImage) -> IndexedImage:
    """Re-anchor a view sprite so its content centres in the ride window's
    112x112 preview box (vanilla previews are hand-drawn 112x112 images
    anchored at (0,0))."""
    return center_in_box(img, PREVIEW_BOX, PREVIEW_BOX)
