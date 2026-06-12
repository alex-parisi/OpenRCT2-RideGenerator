"""
Tests for the stall sprite render plans (shop views, facility door split,
preview anchoring).
"""

import numpy as np
import pytest
from openrct2_object_common.testing import FakeContext
from openrct2_ride_generator.constants import PREVIEW_BOX
from openrct2_ride_generator.sprite_renderer import (
    center_preview,
    count_stall_sprites,
    render_building,
    render_facility,
    render_shop,
    split_facility_mesh,
)
from openrct2_x7_renderer.geometry import face_centroids
from openrct2_x7_renderer.mesh import Mesh, load_mesh
from openrct2_x7_renderer.types import IndexedImage

# One triangle near the +X tile edge (the door band at the default 3.3
# units-per-tile starts at x ~ 0.62) and one at the tile centre.
_DOOR_AND_BODY = (
    "v 1.6 0 0\nv 1.6 0 1\nv 1.6 1 0\n"
    "v 0 0 0\nv 0.2 0 0\nv 0 1 0\n"
    "f 1 2 3\nf 4 5 6\n"
)

_BODY_ONLY = "v 0 0 0\nv 0.2 0 0\nv 0 1 0\nf 1 2 3\n"


def _mesh(tmp_path, text):
    (tmp_path / "m.obj").write_text(text)
    return load_mesh(tmp_path / "m.obj")


def test_count_stall_sprites():
    assert count_stall_sprites("food_stall") == 4
    assert count_stall_sprites("shop") == 4
    assert count_stall_sprites("toilets") == 6
    assert count_stall_sprites("first_aid") == 6
    assert count_stall_sprites("crooked_house") == 4
    assert count_stall_sprites("circus") == 4
    # 4 building views + 72 ghost overlays.
    assert count_stall_sprites("haunted_house") == 76


def test_render_shop_four_views(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_shop(ctx, _mesh(tmp_path, _BODY_ONLY), progress=progress_fn(progress))
    assert len(images) == 4
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_render_shop_empty_mesh_blanks():
    ctx = FakeContext()
    images = render_shop(ctx, Mesh.empty())
    assert len(images) == 4
    assert all(img.width == 1 and img.height == 1 for img in images)
    assert ctx.events == []


def progress_fn(sink):
    return lambda done, total: sink.append((done, total))


def test_render_building_four_views(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_building(
        ctx, _mesh(tmp_path, _BODY_ONLY), "circus", progress=progress_fn(progress)
    )
    assert len(images) == 4
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_render_building_haunted_house_appends_blank_overlays(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_building(
        ctx, _mesh(tmp_path, _BODY_ONLY), "haunted_house", progress=progress_fn(progress)
    )
    assert len(images) == 76
    # Only the 4 building views render; the ghost overlays are 1x1 blanks.
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert all(img.width == 1 and img.height == 1 for img in images[4:])


def test_split_facility_mesh(tmp_path):
    combined = _mesh(tmp_path, _DOOR_AND_BODY)
    door, body = split_facility_mesh(combined)
    assert door.faces.shape[0] == 1
    assert body.faces.shape[0] == 1
    assert face_centroids(door)[0, 0] == pytest.approx(1.6)
    assert face_centroids(body)[0, 0] < 0.62


def test_split_facility_mesh_scales_with_units_per_tile(tmp_path):
    # At 32 units per tile the door band starts at x = 6; both triangles of the
    # small mesh fall well inside the body.
    combined = _mesh(tmp_path, _DOOR_AND_BODY)
    door, body = split_facility_mesh(combined, units_per_tile=32.0)
    assert door.faces.shape[0] == 0
    assert body.faces.shape[0] == 2


def test_render_facility_six_images_in_order(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_facility(
        ctx, _mesh(tmp_path, _DOOR_AND_BODY), progress=progress_fn(progress)
    )
    assert len(images) == 6
    # door (k=0, 3), full (k=1, 2), body (k=4, 5): all non-empty here.
    assert sum(1 for e in ctx.events if e == "begin") == 6
    assert progress == [(k + 1, 6) for k in range(6)]


def test_render_facility_without_door_faces_blanks_door_slots(tmp_path):
    ctx = FakeContext()
    images = render_facility(ctx, _mesh(tmp_path, _BODY_ONLY))
    assert len(images) == 6
    # k=0 and k=3 (door slabs) are blanks; the other four render.
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert images[0].width == 1 and images[3].width == 1


def test_render_facility_door_split_disabled(tmp_path):
    ctx = FakeContext()
    images = render_facility(ctx, _mesh(tmp_path, _DOOR_AND_BODY), door_split=False)
    assert len(images) == 6
    # The full building fills k=0..3; the body overlays k=4/5 are blank.
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert images[4].width == 1 and images[5].width == 1


def test_render_facility_empty_mesh_all_blank():
    ctx = FakeContext()
    images = render_facility(ctx, Mesh.empty())
    assert len(images) == 6
    assert all(img.width == 1 for img in images)
    assert ctx.events == []


def test_center_preview_offsets():
    img = IndexedImage(
        width=40,
        height=20,
        x_offset=-7,
        y_offset=3,
        pixels=np.zeros((20, 40), dtype=np.uint8),
    )
    out = center_preview(img)
    assert (out.width, out.height) == (40, 20)
    assert out.x_offset == (PREVIEW_BOX - 40) // 2
    assert out.y_offset == (PREVIEW_BOX - 20) // 2
    assert out.pixels is img.pixels
