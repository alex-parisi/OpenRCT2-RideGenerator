"""
Tests for the stall sprite render plans (shop views, facility door split,
preview anchoring).
"""

import numpy as np
from openrct2_object_common.testing import FakeContext
from openrct2_ride_generator.constants import PREVIEW_BOX
from openrct2_ride_generator.sprite_renderer import (
    center_preview,
    count_stall_sprites,
    render_building,
    render_facility,
    render_flat_ride,
    render_shop,
    split_door_strip,
)
from openrct2_x7_renderer.mesh import Mesh, load_mesh
from openrct2_x7_renderer.types import IndexedImage, MeshFrame, Model

_TRI = "v 0 0 0\nv 0.2 0 0\nv 0 1 0\nf 1 2 3\n"

_DOOR_TRI = "v 1.6 0 0\nv 1.6 0 1\nv 1.6 1 0\nf 1 2 3\n"


def _mesh(tmp_path, text, name="m.obj"):
    (tmp_path / name).write_text(text)
    return load_mesh(tmp_path / name)


def _img(rows, x_offset=0, y_offset=0):
    arr = np.array(rows, dtype=np.uint8)
    return IndexedImage(
        width=arr.shape[1],
        height=arr.shape[0],
        x_offset=x_offset,
        y_offset=y_offset,
        pixels=arr,
    )


def test_count_stall_sprites():
    assert count_stall_sprites("food_stall") == 4
    assert count_stall_sprites("shop") == 4
    assert count_stall_sprites("cash_machine") == 4
    assert count_stall_sprites("toilets") == 6
    assert count_stall_sprites("first_aid") == 6
    assert count_stall_sprites("crooked_house") == 4
    assert count_stall_sprites("circus") == 4
    # 4 building views + 72 ghost overlays.
    assert count_stall_sprites("haunted_house") == 76
    # 32 structure rotation frames + 68 blank rider overlays.
    assert count_stall_sprites("merry_go_round") == 100
    # 4 directions x 8 frames + 512 blank rider overlays.
    assert count_stall_sprites("ferris_wheel") == 544


def test_render_shop_four_views(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_shop(ctx, _mesh(tmp_path, _TRI), progress=progress_fn(progress))
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
        ctx, _mesh(tmp_path, _TRI), "circus", progress=progress_fn(progress)
    )
    assert len(images) == 4
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


def _spin_model(n, mesh_index=0):
    """A single placement carrying n rotation poses (one MeshFrame each)."""
    frames = [
        MeshFrame(mesh_index=mesh_index, orientation=np.array([360.0 * i / n, 0, 0]))
        for i in range(n)
    ]
    return Model(meshes=[frames])


def test_render_flat_ride_frames_and_blank_overlays(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(32), "merry_go_round",
        progress=progress_fn(progress),
    )
    # 32 rendered structure frames + 68 blank rider overlays.
    assert len(images) == 100
    assert sum(1 for e in ctx.events if e == "begin") == 32
    assert progress[0] == (1, 32) and progress[-1] == (32, 32)
    assert all(img.width == 1 and img.height == 1 for img in images[32:])


def test_render_flat_ride_ferris_four_directions(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(8), "ferris_wheel",
        progress=progress_fn(progress),
    )
    # 4 directions x 8 frames structure + 512 blank rider overlays.
    assert len(images) == 544
    assert sum(1 for e in ctx.events if e == "begin") == 32
    assert progress[-1] == (32, 32)
    assert all(img.width == 1 and img.height == 1 for img in images[32:])


def test_render_flat_ride_empty_pose_blanks(tmp_path):
    # A placement that resolves to no geometry (mesh_index -1) renders a blank
    # without opening a scene.
    ctx = FakeContext()
    images = render_flat_ride(ctx, [_mesh(tmp_path, _TRI)], _spin_model(32, -1), "merry_go_round")
    assert len(images) == 100
    assert sum(1 for e in ctx.events if e == "begin") == 0
    assert all(img.width == 1 and img.height == 1 for img in images[:32])


def test_render_building_haunted_house_appends_blank_overlays(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_building(
        ctx, _mesh(tmp_path, _TRI), "haunted_house", progress=progress_fn(progress)
    )
    assert len(images) == 76
    # Only the 4 building views render; the ghost overlays are 1x1 blanks.
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert all(img.width == 1 and img.height == 1 for img in images[4:])


def test_split_door_strip_partitions_columns():
    # 2x4 building, anchored so its columns span screen x = -2 .. 1; the door
    # render's opaque pixels cover screen x = 0 (column 2 of the building).
    full = _img([[1, 2, 3, 4], [5, 6, 7, 8]], x_offset=-2, y_offset=-1)
    door = _img([[0, 9], [0, 9]], x_offset=-1, y_offset=-1)
    strip, body = split_door_strip(full, door)
    assert (strip.width, strip.height) == (1, 2)
    assert (strip.x_offset, strip.y_offset) == (0, -1)
    assert strip.pixels[:, 0].tolist() == [3, 7]
    # The body keeps every other column, with the strip blanked in place.
    assert (body.width, body.height) == (4, 2)
    assert (body.x_offset, body.y_offset) == (-2, -1)
    assert body.pixels[:, 2].tolist() == [0, 0]
    assert body.pixels[:, 0].tolist() == [1, 5]
    assert body.pixels[:, 3].tolist() == [4, 8]


def test_split_door_strip_trims_transparent_borders():
    # Strip column only has content in the bottom row; body loses its
    # rightmost (door) column entirely.
    full = _img([[0, 1, 0], [2, 3, 4]], x_offset=0, y_offset=0)
    door = _img([[5]], x_offset=2, y_offset=0)
    strip, body = split_door_strip(full, door)
    assert (strip.width, strip.height) == (1, 1)
    assert (strip.x_offset, strip.y_offset) == (2, 1)
    assert strip.pixels.tolist() == [[4]]
    assert (body.width, body.height) == (2, 2)
    assert (body.x_offset, body.y_offset) == (0, 0)


def test_split_door_strip_door_spanning_building_empties_body():
    full = _img([[1, 2], [3, 4]], x_offset=0)
    door = _img([[9, 9]], x_offset=0)
    strip, body = split_door_strip(full, door)
    assert strip.pixels.tolist() == [[1, 2], [3, 4]]
    assert (body.width, body.height) == (1, 1)
    assert not body.pixels.any()


def test_split_door_strip_blank_door_returns_full():
    full = _img([[1, 2], [3, 4]])
    strip, body = split_door_strip(full, IndexedImage.blank(1, 1))
    assert strip.width == 1 and strip.height == 1
    assert not strip.pixels.any()
    assert body is full


def test_split_door_strip_door_outside_building_returns_full():
    full = _img([[1, 2], [3, 4]], x_offset=0)
    door = _img([[9]], x_offset=10)
    strip, body = split_door_strip(full, door)
    assert not strip.pixels.any()
    assert body is full


def test_render_facility_six_images_with_door(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_facility(
        ctx,
        _mesh(tmp_path, _TRI),
        _mesh(tmp_path, _DOOR_TRI, "d.obj"),
        progress=progress_fn(progress),
    )
    assert len(images) == 6
    # 4 full-building views + 2 door-locator renders.
    assert sum(1 for e in ctx.events if e == "begin") == 6
    assert progress == [(k + 1, 6) for k in range(6)]


def test_render_facility_without_door_renders_full_views_only(tmp_path):
    ctx = FakeContext()
    progress = []
    images = render_facility(ctx, _mesh(tmp_path, _TRI), progress=progress_fn(progress))
    assert len(images) == 6
    # The full building fills k=0..3; the body overlays k=4/5 are blank.
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert progress == [(k + 1, 4) for k in range(4)]
    assert images[4].width == 1 and images[5].width == 1


def test_render_facility_empty_door_mesh_acts_like_no_door(tmp_path):
    ctx = FakeContext()
    images = render_facility(ctx, _mesh(tmp_path, _TRI), Mesh.empty())
    assert len(images) == 6
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
