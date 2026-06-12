"""
Stall sprite rendering.

Shops (Shop.cpp) paint `base_image_id + direction` with a {0,0} paint offset,
so a stall renders like large scenery: 4 cardinal views, each anchored at the
tile's per-direction reference corner. Facilities (Facility.cpp) paint
`base_image_id + ((direction + 2) & 3)`, splitting directions 1/2 into a
door-wall sprite plus a building-body overlay so peeps sort into the doorway.
"""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.geometry import face_centroids, split_mesh_by_ghost, subset_mesh
from openrct2_x7_renderer.mesh import Mesh
from openrct2_x7_renderer.ray_trace import VIEWS, Context
from openrct2_x7_renderer.types import IndexedImage

from .constants import (
    FACILITY_DOOR_BAND_FRACTION,
    FACILITY_VIEW_SPRITES,
    PREVIEW_BOX,
    SHOP_VIEW_SPRITES,
    STALL_TYPES,
    StallKind,
)

ProgressFn = Callable[[int, int], None]

_IDENTITY3 = np.eye(3, dtype=np.float64)


def count_stall_sprites(stall_type: str) -> int:
    """View sprites for a stall type (the 3 preview slots are extra)."""
    if STALL_TYPES[stall_type] is StallKind.FACILITY:
        return FACILITY_VIEW_SPRITES
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


# The door wall must face the camera at view directions 1 and 2 (where
# Facility.cpp paints it as a separate near-wall slab) and face away at 0 and
# 3. Under this renderer's dimetric camera that is the tile's +X edge, so a
# facility is authored with its door facing OBJ +X.
def split_facility_mesh(combined: Mesh, units_per_tile: float = TILE_SIZE) -> tuple[Mesh, Mesh]:
    """Split a facility into (door_wall, body) by face centroid: faces within
    the door band along the +X edge are the door wall."""
    threshold = units_per_tile / 2.0 - FACILITY_DOOR_BAND_FRACTION * units_per_tile
    in_band = face_centroids(combined)[:, 0] >= threshold
    return subset_mesh(combined, in_band), subset_mesh(combined, ~in_band)


def render_facility(
    context: Context,
    combined: Mesh,
    units_per_tile: float = TILE_SIZE,
    door_split: bool = True,
    progress: ProgressFn | None = None,
) -> list[IndexedImage]:
    """Render a facility sprite set in Facility.cpp's image order.

    Image k serves view direction (k + 2) & 3: k=0/3 are the door-wall slabs
    for directions 2/1, k=1/2 the full building for directions 3/0, and k=4/5
    the building-body overlays for directions 2/1. Without `door_split` the
    full building fills the directional slots and the overlays are blank."""
    if door_split:
        door, body = split_facility_mesh(combined, units_per_tile)
    else:
        door, body = combined, Mesh.empty()

    # (mesh, view direction) in image order k = 0..5.
    plan = [(door, 2), (combined, 3), (combined, 0), (door, 1), (body, 2), (body, 1)]
    images = []
    for k, (mesh, d) in enumerate(plan):
        images.append(_render_direction(context, mesh, d, units_per_tile))
        if progress is not None:
            progress(k + 1, len(plan))
    return images


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
