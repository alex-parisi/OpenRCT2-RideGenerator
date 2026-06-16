"""
Stall sprite rendering.

Shops (Shop.cpp) paint `base_image_id + direction` with a {0,0} paint offset,
so a stall renders like large scenery: 4 cardinal views, each anchored at the
tile's per-direction reference corner. Facilities (Facility.cpp) paint
`base_image_id + ((direction + 2) & 3)`, splitting directions 1/2 into a
doorway sprite plus a building-body overlay so peeps sort into the doorway.
"""

import numpy as np
from openrct2_object_common.export import ProgressFn
from openrct2_object_common.sprite_render import (
    center_in_box,
    render_corner_anchored_view,
    render_scene_view,
    trim,
)
from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.geometry import combine_model_world
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

# The animated flat ride's structure is a vehicle sprite anchored at the entity
# centre (the tile origin), not a tile corner.
_FLAT_RIDE_ANCHOR = np.zeros(3, dtype=np.float64)


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


def render_flat_ride(
    context: Context,
    meshes: list[Mesh],
    model: Model,
    stall_type: str,
    progress: ProgressFn | None = None,
) -> list[IndexedImage]:
    """Render an animated flat ride sprite set: the structure ring (one image per
    view direction and animation pose, in the engine's ``direction * frames +
    frame`` order), followed by blank rider overlays.

    The structure is a vehicle sprite anchored at the tile centre. Each pose
    bakes one frame of the multi-frame ``model`` (the Blender-authored spin); the
    camera direction is the world rotation ``VIEWS[d]``. The merry-go-round is
    rotationally symmetric, so it stores a single direction (the engine folds the
    camera rotation out and reuses the ring); the ferris wheel is not, so it
    stores all four (``FerrisWheel.cpp`` reads ``base + direction * 8 + frame``).

    ``spec.direction_minor`` selects the ring's image order: direction-major
    (``image = direction * frames + frame``, the ferris/carousel layout) or
    direction-minor (``image = frame * directions + direction``, the enterprise
    layout, ``Enterprise.cpp`` reads ``base + (animationFrame << 2) + direction``).
    The trailing rider slots are emitted blank, like the haunted house's ghosts,
    so the engine never paints a stray peep image."""
    spec = FLAT_RIDE_SPECS[stall_type]
    # Each pose's baked mesh is the same across directions, so bake once per pose.
    posed = [combine_model_world(meshes, model, frame=f) for f in range(spec.frames)]
    if spec.direction_minor:
        order = [(d, f) for f in range(spec.frames) for d in range(spec.directions)]
    else:
        order = [(d, f) for d in range(spec.directions) for f in range(spec.frames)]
    images: list[IndexedImage] = []
    total = spec.structure_sprites
    for i, (d, f) in enumerate(order):
        combined = posed[f]
        if combined.faces.shape[0] == 0:
            images.append(IndexedImage.blank(1, 1))
        else:
            images.append(render_scene_view(context, combined, _FLAT_RIDE_ANCHOR, VIEWS[d]))
        if progress is not None:
            progress(i + 1, total)
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
