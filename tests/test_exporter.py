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
    # The triangle mesh sits at the tile centre, so the door slabs render
    # blank; the image count is still the fixed 3 + 6.
    stall = _stall(tmp_path, ride_type="first_aid", sells=None)
    export_stall_to(stall, FakeContext(), tmp_path / "f.parkobj", tmp_path / "w")
    with zipfile.ZipFile(tmp_path / "f.parkobj") as zf:
        j = json.loads(zf.read("object.json"))
    assert j["images"] == ["$LGX:images.dat[0..8]"]


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
    stall = _stall(tmp_path, ride_type="toilets", sells=None)
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    for i in range(6):
        assert (test_dir / f"stall_{i}.png").exists()
    note = (test_dir / "door_split.txt").read_text()
    assert "door 0 faces" in note
    assert "body 1 faces" in note


def test_export_stall_test_facility_split_disabled_no_note(tmp_path):
    stall = _stall(tmp_path, ride_type="toilets", sells=None, facility_door_split=False)
    test_dir = tmp_path / "test"
    export_stall_test(stall, FakeContext(), test_dir)
    assert not (test_dir / "door_split.txt").exists()
