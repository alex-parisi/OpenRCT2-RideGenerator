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
from openrct2_x7_renderer.constants import MeshFlag
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
    assert count_stall_sprites("3d_cinema") == 4
    # 4 building views + 72 ghost overlays.
    assert count_stall_sprites("haunted_house") == 76
    # 32 structure rotation frames + 68 blank rider overlays.
    assert count_stall_sprites("merry_go_round") == 100
    # 4 directions x 8 frames + 512 blank rider overlays.
    assert count_stall_sprites("ferris_wheel") == 544
    # 24 structure rotation frames (symmetric, one direction) + 216 blank riders.
    assert count_stall_sprites("twist") == 240
    # 4 directions x 49 frames + 48 blank rider overlays.
    assert count_stall_sprites("enterprise") == 244
    # 4 directions x 35 tilt poses, no rider overlays.
    assert count_stall_sprites("motion_simulator") == 140
    # 2 planes x 19 swing blocks, each ship sprite trailed by 8 blank riders.
    assert count_stall_sprites("swinging_ship") == 342
    # 4 directions x 88 spin poses + 4*88 blank rider overlays.
    assert count_stall_sprites("space_rings") == 704


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
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(32), Model(), "merry_go_round",
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
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(8), Model(), "ferris_wheel",
        progress=progress_fn(progress),
    )
    # 4 directions x 8 frames structure + 512 blank rider overlays.
    assert len(images) == 544
    assert sum(1 for e in ctx.events if e == "begin") == 32
    assert progress[-1] == (32, 32)
    assert all(img.width == 1 and img.height == 1 for img in images[32:])


def test_render_flat_ride_twist_single_direction(tmp_path):
    ctx = FakeContext()
    images = render_flat_ride(ctx, [_mesh(tmp_path, _TRI)], _spin_model(24), Model(), "twist")
    # 24 structure frames (one symmetric direction) + 216 blank rider overlays.
    assert len(images) == 240
    assert sum(1 for e in ctx.events if e == "begin") == 24
    assert all(img.width == 1 and img.height == 1 for img in images[24:])


def test_render_flat_ride_twist_masks_riders_with_structure(tmp_path):
    # The twist's rider ring is rendered with the structure as a depth-mask
    # occluder so far-side riders are clipped behind the canopy instead of painted
    # over it. Each of the 216 rider sprites opens a scene that adds the structure
    # as a MASK (mask=1) plus the drawn rider (mask=0); the 24 structure frames add
    # no mask occluders.
    ctx = FakeContext()
    rider = Model(meshes=[[
        MeshFrame(mesh_index=1, orientation=np.array([s * 360.0 / 216, 0, 0]))
        for s in range(216)
    ]])
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI), _mesh(tmp_path, _TRI, "r.obj")], _spin_model(24),
        rider, "twist",
    )
    assert len(images) == 240
    # 24 structure + 216 rider scenes, each opening a render.
    assert sum(1 for e in ctx.events if e == "begin") == 240
    # One masked structure occluder added per rider frame (none for the structure
    # ring), so exactly 216 mask=1 adds for the simple single-submesh meshes.
    mask_adds = sum(1 for e in ctx.events if e == ("add", int(MeshFlag.MASK)))
    assert mask_adds == 216


def test_render_flat_ride_carousel_renders_riders(tmp_path):
    # With a rider ring, the 68 carousel rider slots render instead of staying
    # blank: 32 structure + 68 rider images, all 100 rendered.
    ctx = FakeContext()
    progress = []
    rider = Model(meshes=[[
        MeshFrame(mesh_index=1, orientation=np.array([(s + 13) * 360.0 / 128, 0, 0]))
        for s in range(68)
    ]])
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI), _mesh(tmp_path, _TRI, "r.obj")], _spin_model(32),
        rider, "merry_go_round", progress=progress_fn(progress),
    )
    assert len(images) == 100
    # Every slot opens a render scene (structure + riders), so none is a blank.
    assert sum(1 for e in ctx.events if e == "begin") == 100
    assert progress[-1] == (100, 100)


def test_render_flat_ride_ferris_renders_riders(tmp_path):
    # The ferris rider ring is 4 directions x 128 poses; all 512 slots render.
    ctx = FakeContext()
    rider = Model(meshes=[[
        MeshFrame(mesh_index=1, position=np.array([3.0, 3.6, 0.0])) for _ in range(128)
    ]])
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI), _mesh(tmp_path, _TRI, "r.obj")], _spin_model(8),
        rider, "ferris_wheel",
    )
    assert len(images) == 544  # 32 structure + 512 riders
    assert sum(1 for e in ctx.events if e == "begin") == 544


def test_render_flat_ride_space_rings_renders_riders(tmp_path):
    # The space rings rider ring matches the structure: 4 directions x 88, all
    # 352 trailing slots rendered.
    ctx = FakeContext()
    rider = Model(meshes=[[
        MeshFrame(mesh_index=1, orientation=np.array([0, 360.0 * f / 88, 0]))
        for f in range(88)
    ]])
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI), _mesh(tmp_path, _TRI, "r.obj")], _spin_model(88),
        rider, "space_rings",
    )
    assert len(images) == 704  # 352 structure + 352 riders
    assert sum(1 for e in ctx.events if e == "begin") == 704


def test_render_flat_ride_swinging_ship_renders_bench_riders(tmp_path):
    # The 8 sub-slots after each ship sprite render the bench rows in place of
    # blanks: 2 planes x 19 x (1 ship + 8 riders) all rendered.
    ctx = FakeContext()
    rows = [Model(meshes=[[MeshFrame(mesh_index=1) for _ in range(19)]]) for _ in range(8)]
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI), _mesh(tmp_path, _TRI, "r.obj")], _spin_model(19),
        Model(), "swinging_ship", rider_sub_models=rows,
    )
    assert len(images) == 342
    # Every ship sprite and every bench sub-slot opens a render scene.
    assert sum(1 for e in ctx.events if e == "begin") == 342


def test_render_flat_ride_swinging_ship_blank_sub_slots_without_riders(tmp_path):
    # No bench geometry -> the 8 sub-slots stay blank (pre-riders behaviour): only
    # the 2 planes x 19 ship sprites render.
    ctx = FakeContext()
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(19), Model(), "swinging_ship"
    )
    assert len(images) == 342
    assert sum(1 for e in ctx.events if e == "begin") == 38
    assert all(img.width == 1 and img.height == 1 for img in images[1:9])


def test_render_flat_ride_riders_blank_without_geometry(tmp_path):
    # A ride whose rider ring carries no geometry keeps the slots blank (the
    # pre-riders behaviour), so old objects render unchanged.
    ctx = FakeContext()
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(32), Model(), "merry_go_round"
    )
    assert len(images) == 100
    assert all(img.width == 1 and img.height == 1 for img in images[32:])


def _render_view_directions(monkeypatch, ride_type, frames):
    """Record the view direction passed to the corner-anchored render for each
    structure image, so the ring's image order can be asserted."""
    import openrct2_ride_generator.sprite_renderer as sr

    seen = []

    def spy(context, mesh, direction, **kwargs):
        seen.append(direction)
        return IndexedImage.blank(1, 1)

    monkeypatch.setattr(sr, "render_corner_anchored_view", spy)
    ctx = FakeContext()
    images = sr.render_flat_ride(
        ctx, [_mesh_for(frames)], _spin_model(frames), Model(), ride_type
    )
    return seen, images


def _mesh_for(_frames):
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp())
    (d / "m.obj").write_text(_TRI)
    return load_mesh(d / "m.obj")


def test_render_flat_ride_enterprise_interleaved_order(monkeypatch):
    # Enterprise stores the ring direction-minor (image = frame * directions +
    # direction), so the rendered directions cycle 0,1,2,3, 0,1,2,3, ...
    seen, images = _render_view_directions(monkeypatch, "enterprise", 49)
    assert len(images) == 244  # 4 x 49 structure + 48 blank riders
    assert len(seen) == 196
    assert seen[:8] == [0, 1, 2, 3, 0, 1, 2, 3]


def test_render_flat_ride_motion_simulator_interleaved_order(monkeypatch):
    # The motion simulator stores the ring direction-minor like the enterprise
    # (image = frame * directions + direction), with no trailing rider overlays.
    seen, images = _render_view_directions(monkeypatch, "motion_simulator", 35)
    assert len(images) == 140  # 4 x 35 structure, no riders
    assert len(seen) == 140
    assert seen[:8] == [0, 1, 2, 3, 0, 1, 2, 3]


def test_render_flat_ride_swinging_ship_interleaved_blanks(monkeypatch, tmp_path):
    # The swinging ship is direction-minor (2 planes) and trails each ship sprite
    # with 8 blank rider slots: image = swing*18 + plane*9 + sub.
    import openrct2_ride_generator.sprite_renderer as sr

    marker = IndexedImage(
        width=2, height=2, x_offset=0, y_offset=0, pixels=np.ones((2, 2), dtype=np.uint8)
    )
    monkeypatch.setattr(sr, "render_corner_anchored_view", lambda *a, **k: marker)
    ctx = FakeContext()
    images = sr.render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(19), Model(), "swinging_ship"
    )
    assert len(images) == 342  # 2 planes x 19 blocks x (1 ship + 8 blank riders)
    # Block 0: plane-0 ship then 8 blanks, plane-1 ship then 8 blanks.
    assert images[0] is marker
    assert all(img.width == 1 and img.height == 1 for img in images[1:9])
    assert images[9] is marker
    assert all(img.width == 1 and img.height == 1 for img in images[10:18])


def test_render_flat_ride_ferris_direction_major_order(monkeypatch):
    # The ferris wheel stores the ring direction-major (image = direction *
    # frames + frame), so all 8 frames of direction 0 render before direction 1.
    seen, _ = _render_view_directions(monkeypatch, "ferris_wheel", 8)
    assert seen[:9] == [0, 0, 0, 0, 0, 0, 0, 0, 1]


def test_render_flat_ride_empty_pose_blanks(tmp_path):
    # A placement that resolves to no geometry (mesh_index -1) renders a blank
    # without opening a scene.
    ctx = FakeContext()
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(32, -1), Model(), "merry_go_round"
    )
    assert len(images) == 100
    assert sum(1 for e in ctx.events if e == "begin") == 0
    assert all(img.width == 1 and img.height == 1 for img in images[:32])


def test_render_flat_ride_twist_masked_empty_rider_pose_blank(tmp_path):
    # An empty rider pose (mesh_index -1) in the masked twist path renders a blank
    # without opening a scene, even though the structure occluder is available.
    ctx = FakeContext()
    images = render_flat_ride(
        ctx, [_mesh(tmp_path, _TRI)], _spin_model(24), _spin_model(216, -1), "twist"
    )
    assert len(images) == 240
    # Only the 24 structure poses open a scene; the 216 empty rider poses do not.
    assert sum(1 for e in ctx.events if e == "begin") == 24
    assert all(img.width == 1 and img.height == 1 for img in images[24:])


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
