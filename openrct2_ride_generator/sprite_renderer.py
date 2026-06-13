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
from numpy.typing import NDArray
from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.geometry import split_mesh_by_ghost
from openrct2_x7_renderer.mesh import Mesh
from openrct2_x7_renderer.ray_trace import VIEWS, Context
from openrct2_x7_renderer.types import IndexedImage

from .constants import (
    BUILDING_VIEW_SPRITES,
    FACILITY_VIEW_SPRITES,
    HAUNTED_HOUSE_OVERLAY_SPRITES,
    PREVIEW_BOX,
    SHOP_VIEW_SPRITES,
    STALL_TYPES,
    StallKind,
)

ProgressFn = Callable[[int, int], None]

_IDENTITY3 = np.eye(3, dtype=np.float64)


def count_stall_sprites(stall_type: str) -> int:
    """View sprites for a stall type (the 3 preview slots are extra;
    haunted house ghost overlays count as view sprites here)."""
    if STALL_TYPES[stall_type] is StallKind.FACILITY:
        return FACILITY_VIEW_SPRITES
    if STALL_TYPES[stall_type] is StallKind.BUILDING:
        extra = HAUNTED_HOUSE_OVERLAY_SPRITES if stall_type == "haunted_house" else 0
        return BUILDING_VIEW_SPRITES + extra
    return SHOP_VIEW_SPRITES


def _render_scene_view(
    context: Context, mesh: Mesh, translation: NDArray[np.float64], view: NDArray[np.float64]
) -> IndexedImage:
    """Render a single model under a single view in its own scene, splitting
    ghost faces into their own GHOST model so the renderer traces through
    them."""
    with context.begin_render() as scene:
        for sub_mesh, mask in split_mesh_by_ghost(mesh):
            scene.add_model(sub_mesh, _IDENTITY3, translation, mask)
        with scene.finalize() as ready:
            return ready.render_view(view)


# OpenRCT2 anchors a stall sprite at the tile's reference corner (paint offset
# {0,0}), the same per-direction corner pattern as large scenery.
def _corners_by_dir(units_per_tile: float) -> list[tuple[float, float]]:
    h = units_per_tile / 2.0
    return [(h, h), (-h, h), (-h, -h), (h, -h)]


def _render_direction(
    context: Context, mesh: Mesh, direction: int, units_per_tile: float
) -> IndexedImage:
    """Render `mesh` for one view direction, corner-anchored."""
    if mesh.faces.shape[0] == 0:
        return IndexedImage.blank(1, 1)
    ox, oz = _corners_by_dir(units_per_tile)[direction]
    translation = np.array([-ox, 0.0, -oz], dtype=np.float64)
    return _render_scene_view(context, mesh, translation, VIEWS[direction])


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


def _trim(img: IndexedImage) -> IndexedImage:
    """Crop fully transparent borders, keeping the draw anchor."""
    rows = np.flatnonzero(img.pixels.any(axis=1))
    cols = np.flatnonzero(img.pixels.any(axis=0))
    if rows.size == 0:
        return IndexedImage.blank(1, 1)
    r0, r1 = int(rows[0]), int(rows[-1]) + 1
    c0, c1 = int(cols[0]), int(cols[-1]) + 1
    return IndexedImage(
        width=c1 - c0,
        height=r1 - r0,
        x_offset=img.x_offset + c0,
        y_offset=img.y_offset + r0,
        pixels=np.ascontiguousarray(img.pixels[r0:r1, c0:c1]),
    )


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
    return IndexedImage(
        width=img.width,
        height=img.height,
        x_offset=(PREVIEW_BOX - img.width) // 2,
        y_offset=(PREVIEW_BOX - img.height) // 2,
        pixels=img.pixels,
    )
