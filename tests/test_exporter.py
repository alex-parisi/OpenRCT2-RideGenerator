"""
Tests for object.json assembly, images.dat emission, and .parkobj zipping.
"""

import json
import zipfile

import numpy as np
from openrct2_object_common.testing import FakeContext
from openrct2_ride_generator.exporter import (
    build_stall_json,
    export_stall,
    export_stall_test,
    export_stall_to,
)
from openrct2_ride_generator.loader import build_stall
from openrct2_x7_renderer.mesh import load_mesh
from openrct2_x7_renderer.types import IndexedImage

_TRI = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"


def _stall(tmp_path, **overrides):
    (tmp_path / "m.obj").write_text(_TRI)
    config = {
        "id": "openrct2rg.ride.test",
        "name": "Test Stall",
        "description": "A test stall",
        "ride_type": "drink_stall",
        "sells": "lemonade",
        "model": [{"mesh_index": 0, "position": [0, 0, 0]}],
        **overrides,
    }
    config = {k: v for k, v in config.items() if v is not None}
    preview = config.pop("_preview", None)
    return build_stall(config, [load_mesh(tmp_path / "m.obj")], preview)


def test_build_stall_json_shop_shape(tmp_path):
    j = build_stall_json(_stall(tmp_path, original_id="AAAA|TEST    |0000", authors=["A"]))
    assert j["id"] == "openrct2rg.ride.test"
    assert j["originalId"] == "AAAA|TEST    |0000"
    assert j["authors"] == ["A"]
    assert j["objectType"] == "ride"
    p = j["properties"]
    assert p["type"] == "drink_stall"
    assert p["category"] == "stall"
    assert p["clearance"] == 64
    assert p["sells"] == "lemonade"
    assert p["disablePainting"] is True
    assert p["carsPerFlatRide"] == 1
    assert p["carColours"] == [[["black", "black", "black"]]]
    # The engine synthesizes the car entry for stalls.
    assert "cars" not in p
    assert "buildMenuPriority" not in p
    assert j["strings"] == {
        "name": {"en-GB": "Test Stall"},
        "description": {"en-GB": "A test stall"},
    }


def test_build_stall_json_two_sells_emitted_as_list(tmp_path):
    j = build_stall_json(
        _stall(tmp_path, ride_type="information_kiosk", sells=["map", "umbrella"])
    )
    assert j["properties"]["sells"] == ["map", "umbrella"]


def test_build_stall_json_facility_omits_sells_and_painting(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="toilets",
            sells=None,
            disable_painting=False,
            build_menu_priority=7,
        )
    )
    p = j["properties"]
    assert p["type"] == "toilets"
    assert p["clearance"] == 32
    assert "sells" not in p
    assert "disablePainting" not in p
    assert p["buildMenuPriority"] == 7


def test_build_stall_json_colour_presets(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            car_colours=[["yellow", "black", "black"], ["bright_red", "black", "white"]],
        )
    )
    assert j["properties"]["carColours"] == [
        [["yellow", "black", "black"]],
        [["bright_red", "black", "white"]],
    ]


def test_build_stall_json_building_shape(tmp_path):
    j = build_stall_json(_stall(tmp_path, ride_type="circus", sells=None))
    p = j["properties"]
    assert p["type"] == "circus"
    assert p["category"] == "gentle"
    assert p["tabScale"] == 0.5
    assert p["hasShelter"] is True
    assert p["clearance"] == 128
    assert "sells" not in p
    assert p["carsPerFlatRide"] == 1
    car = p["cars"]
    assert car["numSeats"] == 30
    assert car["spacing"] == 139456
    assert car["frames"] == {"flat": True}
    assert car["recalculateSpriteBounds"] is True
    assert len(car["loadingWaypoints"]) == 16
    # The plain test material uses no remap regions.
    assert "hasAdditionalColour1" not in car
    assert "hasAdditionalColour2" not in car
    assert j["strings"]["capacity"] == {"en-GB": "30 guests"}


def test_build_stall_json_3d_cinema_is_thrill(tmp_path):
    # The 3D cinema paints like the other 3x3 buildings but is filed under
    # "thrill" (not gentle), and carries the shared building waypoint table.
    j = build_stall_json(_stall(tmp_path, ride_type="3d_cinema", sells=None))
    p = j["properties"]
    assert p["type"] == "3d_cinema"
    assert p["category"] == "thrill"
    assert p["hasShelter"] is True
    assert p["clearance"] == 128
    assert p["cars"]["numSeats"] == 20
    assert len(p["cars"]["loadingWaypoints"]) == 16


def _flat_frames(n):
    return [
        [{"mesh_index": 0, "position": [0, 0, 0], "orientation": [360.0 * i / n, 0, 0]}]
        for i in range(n)
    ]


def test_build_stall_json_flat_ride_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="merry_go_round",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(32)},
        )
    )
    p = j["properties"]
    assert p["type"] == "merry_go_round"
    assert p["category"] == "gentle"
    assert p["tabScale"] == 0.5
    assert p["hasShelter"] is True
    assert "sells" not in p
    assert p["carsPerFlatRide"] == 1
    car = p["cars"]
    assert car["numSeats"] == 16
    assert car["rotationFrameMask"] == 31
    assert car["tabOffset"] == -24
    assert car["recalculateSpriteBounds"] is True
    assert len(car["loadingWaypoints"]) == 64
    assert j["strings"]["capacity"] == {"en-GB": "16 guests"}


def test_build_stall_json_ferris_wheel_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="ferris_wheel",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(8)},
        )
    )
    p = j["properties"]
    assert p["type"] == "ferris_wheel"
    assert p["category"] == "gentle"
    # The ferris wheel does not shelter guests, unlike the other car-bearing rides.
    assert "hasShelter" not in p
    # The gentle flat rides advance via a plain rotationFrameMask, not rotationMode.
    assert "rotationMode" not in p
    car = p["cars"]
    assert car["numSeats"] == 32
    assert car["rotationFrameMask"] == 7
    assert car["numSegments"] == 0
    assert len(car["loadingWaypoints"]) == 16
    assert j["strings"]["capacity"] == {"en-GB": "32 guests"}


def test_build_stall_json_twist_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="twist",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(24)},
        )
    )
    p = j["properties"]
    assert p["type"] == "twist"
    # The twist is a thrill ride that advances via rotationMode, not a mask.
    assert p["category"] == "thrill"
    assert p["rotationMode"] == 1
    assert "hasShelter" not in p
    car = p["cars"]
    assert car["numSeats"] == 18
    assert "rotationFrameMask" not in car
    assert car["numSegments"] == 4
    assert car["tabOffset"] == -12
    assert len(car["loadingWaypoints"]) == 72
    assert j["strings"]["capacity"] == {"en-GB": "18 guests"}


def test_build_stall_json_enterprise_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="enterprise",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(49)},
        )
    )
    p = j["properties"]
    assert p["type"] == "enterprise"
    assert p["category"] == "thrill"
    assert p["rotationMode"] == 2
    assert "hasShelter" not in p
    car = p["cars"]
    assert car["numSeats"] == 16
    assert "rotationFrameMask" not in car
    assert car["numSegments"] == 8
    assert car["seatsInPairs"] is False
    assert len(car["loadingWaypoints"]) == 64
    assert j["strings"]["capacity"] == {"en-GB": "16 guests"}


def test_build_stall_json_motion_simulator_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="motion_simulator",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(35)},
        )
    )
    p = j["properties"]
    assert p["type"] == "motion_simulator"
    assert p["category"] == "thrill"
    # The pod is cycled via Status::simulatorOperating, so no rotationMode / mask.
    assert "rotationMode" not in p
    assert "hasShelter" not in p
    car = p["cars"]
    assert car["numSeats"] == 8
    assert "rotationFrameMask" not in car
    assert len(car["loadingWaypoints"]) == 16
    assert j["strings"]["capacity"] == {"en-GB": "8 guests"}


def test_build_stall_json_swinging_ship_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="swinging_ship",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(19)},
        )
    )
    p = j["properties"]
    assert p["type"] == "swinging_ship"
    assert p["category"] == "thrill"
    # Swung via Status::swinging (the ride type), so no rotationMode / mask.
    assert "rotationMode" not in p
    assert "hasShelter" not in p
    car = p["cars"]
    assert car["numSeats"] == 16
    # The swinging ship boards via loadingPositions, not a waypoint table.
    assert "loadingWaypoints" not in car
    assert "loadingPositions" in car
    assert j["strings"]["capacity"] == {"en-GB": "16 guests"}


def test_build_stall_json_space_rings_shape(tmp_path):
    j = build_stall_json(
        _stall(
            tmp_path,
            ride_type="space_rings",
            sells=None,
            model=None,
            animation={"frames": _flat_frames(88)},
        )
    )
    p = j["properties"]
    assert p["type"] == "space_rings"
    assert p["category"] == "gentle"
    # The object provides one ring; the engine spawns four.
    assert p["carsPerFlatRide"] == 4
    assert "rotationMode" not in p
    car = p["cars"]
    assert car["numSeats"] == 1
    assert len(car["loadingWaypoints"]) == 16
    assert j["strings"]["capacity"] == {"en-GB": "1 guests"}


def test_build_stall_json_crooked_house_has_no_waypoints(tmp_path):
    j = build_stall_json(_stall(tmp_path, ride_type="crooked_house", sells=None, seats=8))
    car = j["properties"]["cars"]
    assert car["numSeats"] == 8
    assert "loadingWaypoints" not in car
    assert j["strings"]["capacity"] == {"en-GB": "8 guests"}


def test_build_stall_json_building_remap_materials_enable_colours(tmp_path):
    (tmp_path / "r.mtl").write_text(
        "newmtl Remap2\nKd 0.5 0.5 0.5\nnewmtl Remap3\nKd 0.5 0.5 0.5\n"
    )
    (tmp_path / "r.obj").write_text(
        "mtllib r.mtl\n"
        "usemtl Remap2\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        "usemtl Remap3\nv 0 0 1\nv 1 0 1\nv 0 1 1\nf 4 5 6\n"
    )
    config = {
        "id": "openrct2rg.ride.b",
        "name": "B",
        "description": "A building",
        "ride_type": "haunted_house",
        "model": [{"mesh_index": 0, "position": [0, 0, 0]}],
    }
    stall = build_stall(config, [load_mesh(tmp_path / "r.obj")])
    car = build_stall_json(stall)["properties"]["cars"]
    assert car["hasAdditionalColour1"] is True
    assert car["hasAdditionalColour2"] is True


def test_export_stall_to_writes_parkobj_with_seven_images(tmp_path):
    stall = _stall(tmp_path)
    ctx = FakeContext()
    parkobj = tmp_path / "out" / "s.parkobj"
    work = tmp_path / "work"

    export_stall_to(stall, ctx, parkobj, work)

    assert parkobj.exists()
    with zipfile.ZipFile(parkobj) as zf:
        assert set(zf.namelist()) == {"object.json", "images.dat"}
        j = json.loads(zf.read("object.json"))
    # 3 preview slots + 4 shop views.
    assert j["images"] == ["$LGX:images.dat[0..6]"]
    assert j["objectType"] == "ride"
    assert sum(1 for e in ctx.events if e == "begin") == 4
    assert (work / "images.dat").exists()


def test_export_stall_to_facility_nine_images(tmp_path):
    # No door-marked placement, so the door split is skipped; the image count
    # is still the fixed 3 + 6 (door/body slots emitted blank).
    stall = _stall(tmp_path, ride_type="first_aid", sells=None)
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "f.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "f.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..8]"]
    assert sum(1 for e in ctx.events if e == "begin") == 4


def test_export_stall_to_facility_with_door_renders_door_passes(tmp_path):
    stall = _stall(
        tmp_path,
        ride_type="first_aid",
        sells=None,
        model=[{"mesh_index": 0}, {"mesh_index": 0, "door": True}],
    )
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "f.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "f.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..8]"]
    # 4 full-building views + 2 door-locator renders.
    assert sum(1 for e in ctx.events if e == "begin") == 6


def test_export_stall_to_building_seven_images(tmp_path):
    stall = _stall(tmp_path, ride_type="crooked_house", sells=None)
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "b.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "b.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..6]"]
    assert sum(1 for e in ctx.events if e == "begin") == 4


def test_export_stall_to_haunted_house_includes_ghost_blanks(tmp_path):
    stall = _stall(tmp_path, ride_type="haunted_house", sells=None)
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "h.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "h.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    # 3 previews + 4 views + 72 blank ghost overlays.
    assert j["images"] == ["$LGX:images.dat[0..78]"]
    assert sum(1 for e in ctx.events if e == "begin") == 4


def test_export_stall_to_flat_ride_includes_rider_blanks(tmp_path):
    stall = _stall(
        tmp_path, ride_type="merry_go_round", sells=None, model=None,
        animation={"frames": _flat_frames(32)},
    )
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "m.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "m.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    # 3 previews + 32 structure frames + 68 blank rider overlays.
    assert j["images"] == ["$LGX:images.dat[0..102]"]
    assert sum(1 for e in ctx.events if e == "begin") == 32


def test_export_stall_to_flat_ride_renders_riders(tmp_path):
    # A carousel with a rider ring fills the 68 rider slots instead of blanking
    # them: same image count, but every slot opens a render scene.
    (tmp_path / "m.obj").write_text(_TRI)
    mesh = load_mesh(tmp_path / "m.obj")
    config = {
        "id": "openrct2rg.ride.test",
        "name": "Test Ride",
        "description": "A test ride",
        "ride_type": "merry_go_round",
        "animation": {"frames": _flat_frames(32)},
        "rider_animation": {
            "frames": [
                [{"mesh_index": 1, "position": [0, 0, 0],
                  "orientation": [360.0 * i / 68, 0, 0]}]
                for i in range(68)
            ]
        },
    }
    stall = build_stall(config, [mesh, mesh])
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "r.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "r.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    # 3 previews + 32 structure frames + 68 rendered rider overlays.
    assert j["images"] == ["$LGX:images.dat[0..102]"]
    assert sum(1 for e in ctx.events if e == "begin") == 100


def test_export_stall_to_swinging_ship_renders_bench_riders(tmp_path):
    # The swinging ship's 8 interleaved bench sub-slots render instead of blanking,
    # flowing the rider_sub_models through the full export.
    (tmp_path / "m.obj").write_text(_TRI)
    mesh = load_mesh(tmp_path / "m.obj")
    config = {
        "id": "openrct2rg.ride.test",
        "name": "Test Ride",
        "description": "A test ride",
        "ride_type": "swinging_ship",
        "animation": {"frames": _flat_frames(19)},
        "rider_rows": [
            {"frames": [[{"mesh_index": 1, "position": [0, 0, 0], "orientation": [0, a, 0]}]
                        for a in range(19)]}
            for _ in range(8)
        ],
    }
    stall = build_stall(config, [mesh, mesh])
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "s.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "s.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    # 3 previews + 2 planes x 19 x (1 ship + 8 bench riders) = 3 + 342.
    assert j["images"] == ["$LGX:images.dat[0..344]"]
    assert sum(1 for e in ctx.events if e == "begin") == 342


def test_export_stall_to_ferris_wheel_four_directions(tmp_path):
    stall = _stall(
        tmp_path, ride_type="ferris_wheel", sells=None, model=None,
        animation={"frames": _flat_frames(8)},
    )
    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "f.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "f.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    # 3 previews + 4 directions x 8 frames + 512 blank rider overlays.
    assert j["images"] == ["$LGX:images.dat[0..546]"]
    assert sum(1 for e in ctx.events if e == "begin") == 32


def test_export_stall_test_building_writes_only_view_pngs(tmp_path):
    stall = _stall(tmp_path, ride_type="haunted_house", sells=None)
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    for i in range(4):
        assert (test_dir / f"stall_{i}.png").exists()
    # The 72 blank ghost overlays are not written.
    assert not (test_dir / "stall_4.png").exists()
    assert (test_dir / "preview.png").exists()


def test_export_stall_to_skip_render_reuses_previous_images(tmp_path):
    stall = _stall(tmp_path)
    work = tmp_path / "work"
    export_stall_to(stall, FakeContext(), tmp_path / "a.parkobj", work)

    ctx = FakeContext()
    export_stall_to(stall, ctx, tmp_path / "b.parkobj", work, skip_render=True)
    assert ctx.events == []
    with zipfile.ZipFile(tmp_path / "b.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..6]"]


def test_export_stall_uses_output_directory_and_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stall = _stall(tmp_path)
    out = tmp_path / "dist"
    export_stall(stall, FakeContext(), out)
    assert (out / "openrct2rg.ride.test.parkobj").exists()
    # The default work dir is ./object.
    assert (tmp_path / "object" / "images.dat").exists()


def test_export_stall_to_progress_reaches_total(tmp_path):
    stall = _stall(tmp_path)
    seen = []
    export_stall_to(
        stall,
        FakeContext(),
        tmp_path / "p.parkobj",
        tmp_path / "w",
        progress=lambda done, total: seen.append((done, total)),
    )
    assert seen[-1] == (4, 4)


def test_explicit_preview_image_is_used(tmp_path):
    marker = IndexedImage(
        width=2, height=2, x_offset=0, y_offset=0, pixels=np.full((2, 2), 9, np.uint8)
    )
    stall = _stall(tmp_path, _preview=marker)
    assert stall.preview is marker
    export_stall_to(stall, FakeContext(), tmp_path / "s.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "s.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..6]"]


def test_export_stall_test_writes_pngs(tmp_path):
    stall = _stall(tmp_path)
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    for i in range(4):
        assert (test_dir / f"stall_{i}.png").exists()
    assert (test_dir / "preview.png").exists()
    assert (test_dir / "preview_combined.png").exists()
    assert not (test_dir / "door_split.txt").exists()


def test_export_stall_test_facility_reports_door_split(tmp_path):
    stall = _stall(
        tmp_path,
        ride_type="toilets",
        sells=None,
        model=[{"mesh_index": 0}, {"mesh_index": 0, "door": True}],
    )
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    for i in range(6):
        assert (test_dir / f"stall_{i}.png").exists()
    note = (test_dir / "door_split.txt").read_text()
    assert "door 1 faces" in note


def test_export_stall_test_facility_split_disabled_no_note(tmp_path):
    stall = _stall(tmp_path, ride_type="toilets", sells=None, facility_door_split=False)
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    assert not (test_dir / "door_split.txt").exists()
