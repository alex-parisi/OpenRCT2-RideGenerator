"""
Tests for config parsing and validation (loader).
"""

import json
import logging

import pytest
from openrct2_object_common.config import LoadError
from openrct2_ride_generator.constants import (
    DEFAULT_CLEARANCE,
    DEFAULT_NUM_SEATS,
    STALL_TYPES,
    StallKind,
)
from openrct2_ride_generator.loader import build_stall, load_stall, object_type_of
from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.mesh import load_mesh

_TRI = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"


def _meshes(tmp_path):
    (tmp_path / "m.obj").write_text(_TRI)
    return [load_mesh(tmp_path / "m.obj")]


def _config(**overrides):
    config = {
        "id": "openrct2rg.ride.test",
        "name": "Test Stall",
        "description": "A test stall",
        "ride_type": "food_stall",
        "sells": "ice_cream",
        "model": [{"mesh_index": 0, "position": [0, 0, 0]}],
    }
    config.update(overrides)
    return {k: v for k, v in config.items() if v is not None}


def test_build_stall_minimal(tmp_path):
    stall = build_stall(_config(), _meshes(tmp_path))
    assert stall.id == "openrct2rg.ride.test"
    assert stall.name == "Test Stall"
    assert stall.description == "A test stall"
    assert stall.stall_type == "food_stall"
    assert stall.sells == ["ice_cream"]
    assert stall.clearance == DEFAULT_CLEARANCE["food_stall"]
    assert stall.disable_painting is True
    assert stall.car_colours == [["black", "black", "black"]]
    assert stall.build_menu_priority == 0
    assert stall.facility_door_split is True
    assert stall.units_per_tile == TILE_SIZE
    assert stall.version == "1.0"
    assert stall.preview is None
    assert stall.kind is StallKind.SHOP
    assert stall.num_view_sprites == 4
    assert stall.num_sprites == 7


def test_build_stall_full_fields(tmp_path):
    stall = build_stall(
        _config(
            original_id="AAAA|TEST    |0000",
            authors=["A", "B"],
            version="2.0",
            units_per_tile=32.0,
            clearance=80,
            disable_painting=False,
            car_colours=[["yellow", "black", "white"]],
            build_menu_priority=3,
        ),
        _meshes(tmp_path),
    )
    assert stall.original_id == "AAAA|TEST    |0000"
    assert stall.authors == ["A", "B"]
    assert stall.version == "2.0"
    assert stall.units_per_tile == 32.0
    assert stall.clearance == 80
    assert stall.disable_painting is False
    assert stall.car_colours == [["yellow", "black", "white"]]
    assert stall.build_menu_priority == 3


def test_facility_kind_and_sprite_counts(tmp_path):
    stall = build_stall(
        _config(ride_type="toilets", sells=None), _meshes(tmp_path)
    )
    assert stall.kind is StallKind.FACILITY
    assert stall.num_view_sprites == 6
    assert stall.num_sprites == 9
    assert stall.clearance == DEFAULT_CLEARANCE["toilets"]


@pytest.mark.parametrize("ride_type", sorted(STALL_TYPES))
def test_per_type_clearance_defaults(tmp_path, ride_type):
    sells = "drink" if STALL_TYPES[ride_type] is StallKind.SHOP else None
    stall = build_stall(_config(ride_type=ride_type, sells=sells), _meshes(tmp_path))
    assert stall.clearance == DEFAULT_CLEARANCE[ride_type]


def test_building_kind_and_sprite_counts(tmp_path):
    stall = build_stall(
        _config(ride_type="crooked_house", sells=None), _meshes(tmp_path)
    )
    assert stall.kind is StallKind.BUILDING
    assert stall.num_view_sprites == 4
    assert stall.num_overlay_sprites == 0
    assert stall.num_sprites == 7
    assert stall.clearance == DEFAULT_CLEARANCE["crooked_house"]
    assert stall.num_seats == DEFAULT_NUM_SEATS["crooked_house"]


def test_haunted_house_counts_ghost_overlays(tmp_path):
    stall = build_stall(
        _config(ride_type="haunted_house", sells=None), _meshes(tmp_path)
    )
    assert stall.num_view_sprites == 4
    assert stall.num_overlay_sprites == 72
    assert stall.num_sprites == 79


def test_building_seats_override(tmp_path):
    stall = build_stall(
        _config(ride_type="circus", sells=None, seats=12), _meshes(tmp_path)
    )
    assert stall.num_seats == 12


def test_seats_on_stall_rejected(tmp_path):
    with pytest.raises(LoadError, match="seats"):
        build_stall(_config(seats=8), _meshes(tmp_path))


def test_seats_at_default_value_on_stall_still_rejected(tmp_path):
    # A non-building ride may not declare "seats" at all; presence is rejected
    # regardless of value, even when it equals the implicit default (0).
    with pytest.raises(LoadError, match="seats"):
        build_stall(_config(seats=0), _meshes(tmp_path))


@pytest.mark.parametrize("seats", [0, 256])
def test_building_seats_out_of_range_rejected(tmp_path, seats):
    with pytest.raises(LoadError, match="seats"):
        build_stall(
            _config(ride_type="circus", sells=None, seats=seats), _meshes(tmp_path)
        )


def test_sells_on_building_rejected(tmp_path):
    with pytest.raises(LoadError, match="building"):
        build_stall(
            _config(ride_type="crooked_house", sells="balloon"), _meshes(tmp_path)
        )


def test_sells_list_of_two(tmp_path):
    stall = build_stall(
        _config(ride_type="information_kiosk", sells=["map", "umbrella"]),
        _meshes(tmp_path),
    )
    assert stall.sells == ["map", "umbrella"]


def test_missing_ride_type_rejected(tmp_path):
    with pytest.raises(LoadError):
        build_stall(_config(ride_type=None), _meshes(tmp_path))


def test_unknown_ride_type_rejected(tmp_path):
    with pytest.raises(LoadError, match="merry_go_round"):
        build_stall(_config(ride_type="merry_go_round"), _meshes(tmp_path))


def test_unknown_shop_item_rejected(tmp_path):
    with pytest.raises(LoadError, match="lobster"):
        build_stall(_config(sells="lobster"), _meshes(tmp_path))


def test_non_string_shop_item_rejected(tmp_path):
    with pytest.raises(LoadError, match="sells"):
        build_stall(_config(sells=[1]), _meshes(tmp_path))


def test_too_many_sells_rejected(tmp_path):
    with pytest.raises(LoadError, match="max 2"):
        build_stall(
            _config(sells=["map", "umbrella", "balloon"]), _meshes(tmp_path)
        )


@pytest.mark.parametrize("ride_type", ["toilets", "first_aid"])
def test_sells_on_facility_rejected(tmp_path, ride_type):
    with pytest.raises(LoadError, match="facility"):
        build_stall(_config(ride_type=ride_type, sells="drink"), _meshes(tmp_path))


def test_food_stall_without_sells_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        stall = build_stall(_config(sells=None), _meshes(tmp_path))
    assert stall.sells == []
    assert "sell nothing" in caplog.text


def test_shop_without_sells_is_silent(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        stall = build_stall(_config(ride_type="shop", sells=None), _meshes(tmp_path))
    assert stall.sells == []
    assert caplog.text == ""


@pytest.mark.parametrize("clearance", [0, 256])
def test_clearance_out_of_range_rejected(tmp_path, clearance):
    with pytest.raises(LoadError, match="clearance"):
        build_stall(_config(clearance=clearance), _meshes(tmp_path))


@pytest.mark.parametrize(
    "car_colours",
    [
        "black",
        [],
        [["black", "black"]],
        ["black"],
        [["black", "black", "chartreuse"]],
    ],
)
def test_bad_car_colours_rejected(tmp_path, car_colours):
    with pytest.raises(LoadError):
        build_stall(_config(car_colours=car_colours), _meshes(tmp_path))


def test_missing_name_rejected(tmp_path):
    with pytest.raises(LoadError, match="name"):
        build_stall(_config(name=None), _meshes(tmp_path))


def test_missing_description_rejected(tmp_path):
    with pytest.raises(LoadError, match="description"):
        build_stall(_config(description=None), _meshes(tmp_path))


def test_bad_units_per_tile_rejected(tmp_path):
    with pytest.raises(LoadError, match="units_per_tile"):
        build_stall(_config(units_per_tile=0.0), _meshes(tmp_path))


def test_missing_model_rejected(tmp_path):
    with pytest.raises(LoadError, match="model"):
        build_stall(_config(model=None), _meshes(tmp_path))


def test_model_non_object_entry_rejected(tmp_path):
    with pytest.raises(LoadError, match="model"):
        build_stall(_config(model=["nope"]), _meshes(tmp_path))


@pytest.mark.parametrize("mesh_index", [None, True, 1, -2])
def test_model_bad_mesh_index_rejected(tmp_path, mesh_index):
    entry = {"position": [0, 0, 0]}
    if mesh_index is not None:
        entry["mesh_index"] = mesh_index
    with pytest.raises(LoadError):
        build_stall(_config(model=[entry]), _meshes(tmp_path))


def test_model_empty_slot_and_orientation(tmp_path):
    stall = build_stall(
        _config(
            model=[
                {"mesh_index": -1},
                {"mesh_index": 0, "position": [1, 2, 3], "orientation": [0, 90, 0]},
            ]
        ),
        _meshes(tmp_path),
    )
    assert len(stall.model.meshes) == 2
    assert stall.model.meshes[0][0].mesh_index == -1
    assert list(stall.model.meshes[1][0].orientation) == [0, 90, 0]
    assert stall.door_model.meshes == []


def test_facility_door_marked_placements(tmp_path):
    stall = build_stall(
        _config(
            ride_type="toilets",
            sells=None,
            model=[
                {"mesh_index": 0},
                {"mesh_index": 0, "position": [1, 0, 0], "door": True},
            ],
        ),
        _meshes(tmp_path),
    )
    assert len(stall.model.meshes) == 2
    assert len(stall.door_model.meshes) == 1
    # The door model shares the placement (same frame) with the full model.
    assert stall.door_model.meshes[0] is stall.model.meshes[1]


def test_door_flag_on_shop_rejected(tmp_path):
    with pytest.raises(LoadError, match="door"):
        build_stall(
            _config(model=[{"mesh_index": 0, "door": True}]),
            _meshes(tmp_path),
        )


def test_non_bool_door_flag_rejected(tmp_path):
    with pytest.raises(LoadError, match="door"):
        build_stall(
            _config(
                ride_type="toilets",
                sells=None,
                model=[{"mesh_index": 0, "door": "yes"}],
            ),
            _meshes(tmp_path),
        )


def test_facility_without_door_mark_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_stall(_config(ride_type="toilets", sells=None), _meshes(tmp_path))
    assert "door" in caplog.text


def test_facility_split_disabled_no_door_warning(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_stall(
            _config(ride_type="toilets", sells=None, facility_door_split=False),
            _meshes(tmp_path),
        )
    assert caplog.text == ""


def test_load_stall_from_json_file(tmp_path):
    (tmp_path / "m.obj").write_text(_TRI)
    config = _config(meshes=["m.obj"])
    (tmp_path / "stall.json").write_text(json.dumps(config))
    stall = load_stall(tmp_path / "stall.json")
    assert stall.stall_type == "food_stall"
    assert len(stall.meshes) == 1


def test_load_stall_from_yaml_file(tmp_path):
    (tmp_path / "m.obj").write_text(_TRI)
    (tmp_path / "stall.yaml").write_text(
        "id: openrct2rg.ride.y\n"
        "name: Y\n"
        "description: A yaml stall\n"
        "ride_type: shop\n"
        "sells: balloon\n"
        "meshes: [m.obj]\n"
        "model:\n"
        "  - {mesh_index: 0, position: [0, 0, 0]}\n"
    )
    stall = load_stall(tmp_path / "stall.yaml")
    assert stall.stall_type == "shop"
    assert stall.sells == ["balloon"]


def test_object_type_of_defaults_to_ride():
    assert object_type_of({}) == "ride"
    assert object_type_of({"object_type": "ride"}) == "ride"


def test_object_type_of_rejects_unknown():
    with pytest.raises(LoadError, match="scenery_small"):
        object_type_of({"object_type": "scenery_small"})
