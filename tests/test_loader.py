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
    FLAT_RIDE_SPECS,
    SHOP_SELL_TYPES,
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


def _spin_frames(n):
    """A minimal flat-ride spin: n poses rotating mesh 0 about +Y."""
    return [
        [{"mesh_index": 0, "position": [0, 0, 0], "orientation": [360.0 * i / n, 0, 0]}]
        for i in range(n)
    ]


def _flat_config(ride_type="merry_go_round", **overrides):
    """A valid animated flat-ride config (animation.frames instead of model)."""
    cfg = {
        "id": "openrct2rg.ride.test",
        "name": "Test Ride",
        "description": "A test ride",
        "ride_type": ride_type,
        "animation": {"frames": _spin_frames(FLAT_RIDE_SPECS[ride_type].frames)},
    }
    cfg.update(overrides)
    return {k: v for k, v in cfg.items() if v is not None}


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
    if STALL_TYPES[ride_type] is StallKind.FLAT_RIDE:
        cfg = _flat_config(ride_type=ride_type)
    else:
        sells = "drink" if ride_type in SHOP_SELL_TYPES else None
        cfg = _config(ride_type=ride_type, sells=sells)
    stall = build_stall(cfg, _meshes(tmp_path))
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


def test_flat_ride_kind_and_sprite_counts(tmp_path):
    stall = build_stall(_flat_config(), _meshes(tmp_path))
    assert stall.kind is StallKind.FLAT_RIDE
    assert stall.stall_type == "merry_go_round"
    # 32 structure rotation frames + 68 blank rider overlays, after 3 previews.
    assert stall.num_view_sprites == 32
    assert stall.num_overlay_sprites == 68
    assert stall.num_sprites == 103
    assert stall.clearance == DEFAULT_CLEARANCE["merry_go_round"]
    assert stall.num_seats == DEFAULT_NUM_SEATS["merry_go_round"]
    # One MeshFrame per pose lives on the single placement.
    assert len(stall.model.meshes) == 1
    assert len(stall.model.meshes[0]) == 32


def test_ferris_wheel_kind_and_sprite_counts(tmp_path):
    stall = build_stall(_flat_config("ferris_wheel"), _meshes(tmp_path))
    assert stall.kind is StallKind.FLAT_RIDE
    assert stall.stall_type == "ferris_wheel"
    # 4 directions x 8 frames structure + 512 blank rider overlays, after previews.
    assert stall.num_view_sprites == 32
    assert stall.num_overlay_sprites == 512
    assert stall.num_sprites == 547
    assert stall.clearance == DEFAULT_CLEARANCE["ferris_wheel"]
    assert stall.num_seats == DEFAULT_NUM_SEATS["ferris_wheel"]
    # 8 spin poses on the placement (the example adds orbiting gondolas).
    assert len(stall.model.meshes[0]) == 8


def test_twist_kind_and_sprite_counts(tmp_path):
    stall = build_stall(_flat_config("twist"), _meshes(tmp_path))
    assert stall.kind is StallKind.FLAT_RIDE
    assert stall.stall_type == "twist"
    # 24 structure rotation frames (one symmetric direction) + 216 blank riders.
    assert stall.num_view_sprites == 24
    assert stall.num_overlay_sprites == 216
    assert stall.num_sprites == 243
    assert stall.clearance == DEFAULT_CLEARANCE["twist"]
    assert stall.num_seats == DEFAULT_NUM_SEATS["twist"]
    assert len(stall.model.meshes[0]) == 24


def test_enterprise_kind_and_sprite_counts(tmp_path):
    stall = build_stall(_flat_config("enterprise"), _meshes(tmp_path))
    assert stall.kind is StallKind.FLAT_RIDE
    assert stall.stall_type == "enterprise"
    # 4 directions x 49 frames structure + 48 blank rider overlays, after previews.
    assert stall.num_view_sprites == 196
    assert stall.num_overlay_sprites == 48
    assert stall.num_sprites == 247
    assert stall.clearance == DEFAULT_CLEARANCE["enterprise"]
    assert stall.num_seats == DEFAULT_NUM_SEATS["enterprise"]
    assert len(stall.model.meshes[0]) == 49


def test_flat_ride_seats_override(tmp_path):
    stall = build_stall(_flat_config(seats=24), _meshes(tmp_path))
    assert stall.num_seats == 24


def test_flat_ride_wrong_frame_count_rejected(tmp_path):
    cfg = _flat_config()
    cfg["animation"]["frames"] = cfg["animation"]["frames"][:8]
    with pytest.raises(LoadError, match="exactly 32 animation frames"):
        build_stall(cfg, _meshes(tmp_path))


def test_enterprise_wrong_frame_count_rejected(tmp_path):
    cfg = _flat_config("enterprise")
    cfg["animation"]["frames"] = cfg["animation"]["frames"][:24]
    with pytest.raises(LoadError, match="exactly 49 animation frames"):
        build_stall(cfg, _meshes(tmp_path))


def test_flat_ride_missing_animation_rejected(tmp_path):
    cfg = _flat_config()
    del cfg["animation"]
    with pytest.raises(LoadError, match="animation"):
        build_stall(cfg, _meshes(tmp_path))


def test_flat_ride_empty_frames_rejected(tmp_path):
    cfg = _flat_config()
    cfg["animation"] = {"frames": []}
    with pytest.raises(LoadError, match="animation.frames"):
        build_stall(cfg, _meshes(tmp_path))


def test_flat_ride_uneven_frame_entries_rejected(tmp_path):
    frames = _spin_frames(32)
    # Give the first pose two placements while the rest have one.
    frames[0] = [
        {"mesh_index": 0, "position": [0, 0, 0], "orientation": [0, 0, 0]},
        {"mesh_index": 0, "position": [0, 0, 0], "orientation": [0, 0, 0]},
    ]
    cfg = _flat_config()
    cfg["animation"] = {"frames": frames}
    with pytest.raises(LoadError, match="same number of model entries"):
        build_stall(cfg, _meshes(tmp_path))


def test_flat_ride_static_model_rejected(tmp_path):
    cfg = _flat_config(model=[{"mesh_index": 0, "position": [0, 0, 0]}])
    with pytest.raises(LoadError, match="animation.frames"):
        build_stall(cfg, _meshes(tmp_path))


def _two_meshes(tmp_path):
    (tmp_path / "m.obj").write_text(_TRI)
    return [load_mesh(tmp_path / "m.obj"), load_mesh(tmp_path / "m.obj")]


def _rider_frames(n, mesh_index=1):
    return [
        [{"mesh_index": mesh_index, "position": [0, 0, 0], "orientation": [360.0 * i / n, 0, 0]}]
        for i in range(n)
    ]


def test_flat_ride_rider_animation_loaded(tmp_path):
    spec = FLAT_RIDE_SPECS["merry_go_round"]
    cfg = _flat_config(rider_animation={"frames": _rider_frames(spec.rider_frames)})
    stall = build_stall(cfg, _two_meshes(tmp_path))
    assert len(stall.rider_model.meshes) == 1
    assert len(stall.rider_model.meshes[0]) == spec.rider_frames
    # The rider mesh (index 1) is excluded from the structure's colour flags.
    assert stall.rider_mesh_indices == {1}


def test_flat_ride_no_rider_animation_leaves_riders_empty(tmp_path):
    stall = build_stall(_flat_config(), _meshes(tmp_path))
    assert stall.rider_model.meshes == []
    assert stall.rider_mesh_indices == set()


def test_flat_ride_rider_animation_wrong_count_rejected(tmp_path):
    cfg = _flat_config(rider_animation={"frames": _rider_frames(10)})
    with pytest.raises(LoadError, match="rider ring needs exactly 68"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_flat_ride_without_rider_ring_rejects_rider_animation(tmp_path):
    # The motion simulator's pod is enclosed, so it has no rider ring.
    cfg = _flat_config(ride_type="motion_simulator", rider_animation={"frames": _rider_frames(10)})
    with pytest.raises(LoadError, match="no rider ring"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_swinging_ship_rider_rows_loaded(tmp_path):
    spec = FLAT_RIDE_SPECS["swinging_ship"]
    rows = [
        {"frames": [[{"mesh_index": 1, "position": [0, 0, 0], "orientation": [0, a, 0]}]
                    for a in range(spec.frames)]}
        for _ in range(spec.blank_sub_slots)
    ]
    cfg = _flat_config(ride_type="swinging_ship", rider_rows=rows)
    stall = build_stall(cfg, _two_meshes(tmp_path))
    assert len(stall.rider_sub_models) == spec.blank_sub_slots
    assert all(len(m.meshes[0]) == spec.frames for m in stall.rider_sub_models)
    assert stall.rider_mesh_indices == {1}


def test_swinging_ship_rider_rows_wrong_count_rejected(tmp_path):
    cfg = _flat_config(ride_type="swinging_ship", rider_rows=[{"frames": []}])
    with pytest.raises(LoadError, match="exactly 8 rider_rows"):
        build_stall(cfg, _two_meshes(tmp_path))


def _swing_rows(frames=19):
    return [
        {"frames": [[{"mesh_index": 1, "position": [0, 0, 0], "orientation": [0, a, 0]}]
                    for a in range(frames)]}
        for _ in range(8)
    ]


def test_swinging_ship_rider_rows_not_a_list_rejected(tmp_path):
    cfg = _flat_config(ride_type="swinging_ship", rider_rows="nope")
    with pytest.raises(LoadError, match="must be a list of bench rows"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_swinging_ship_rider_row_not_object_rejected(tmp_path):
    rows = _swing_rows()
    rows[0] = ["not a dict"]
    cfg = _flat_config(ride_type="swinging_ship", rider_rows=rows)
    with pytest.raises(LoadError, match='must be an object with a "frames"'):
        build_stall(cfg, _two_meshes(tmp_path))


def test_swinging_ship_rider_row_wrong_frame_count_rejected(tmp_path):
    rows = _swing_rows()
    rows[0] = {"frames": rows[0]["frames"][:5]}
    cfg = _flat_config(ride_type="swinging_ship", rider_rows=rows)
    with pytest.raises(LoadError, match="needs exactly 19 frames"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_swinging_ship_rider_row_uneven_entries_rejected(tmp_path):
    rows = _swing_rows()
    rows[0]["frames"][0] = rows[0]["frames"][0] + [
        {"mesh_index": 1, "position": [0, 0, 0], "orientation": [0, 0, 0]}
    ]
    cfg = _flat_config(ride_type="swinging_ship", rider_rows=rows)
    with pytest.raises(LoadError, match="same number of model entries"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_flat_ride_spec_supports_riders():
    assert FLAT_RIDE_SPECS["merry_go_round"].supports_riders  # trailing ring
    assert FLAT_RIDE_SPECS["swinging_ship"].supports_riders  # interleaved sub-slots
    assert not FLAT_RIDE_SPECS["motion_simulator"].supports_riders  # enclosed pod


def test_rider_rows_on_ringless_ride_rejected(tmp_path):
    # The twist uses a trailing ring, not interleaved rows.
    cfg = _flat_config(ride_type="twist", rider_rows=[{"frames": []}])
    with pytest.raises(LoadError, match="no rider rows"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_non_flat_ride_rejects_rider_rows(tmp_path):
    cfg = _config(rider_rows=[{"frames": []}])
    with pytest.raises(LoadError, match="no rider rows"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_non_flat_ride_rejects_rider_animation(tmp_path):
    cfg = _config(rider_animation={"frames": _rider_frames(10)})
    with pytest.raises(LoadError, match="no rider ring"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_rider_animation_not_object_rejected(tmp_path):
    cfg = _flat_config(rider_animation=[])
    with pytest.raises(LoadError, match='"rider_animation" must be an object'):
        build_stall(cfg, _two_meshes(tmp_path))


def test_rider_animation_empty_frames_rejected(tmp_path):
    cfg = _flat_config(rider_animation={"frames": []})
    with pytest.raises(LoadError, match="rider_animation.frames"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_rider_animation_uneven_entries_rejected(tmp_path):
    frames = _rider_frames(FLAT_RIDE_SPECS["merry_go_round"].rider_frames)
    frames[0] = frames[0] + [{"mesh_index": 1, "position": [0, 0, 0], "orientation": [0, 0, 0]}]
    cfg = _flat_config(rider_animation={"frames": frames})
    with pytest.raises(LoadError, match="same number of model entries"):
        build_stall(cfg, _two_meshes(tmp_path))


def test_sells_on_flat_ride_rejected(tmp_path):
    with pytest.raises(LoadError, match="merry_go_round"):
        build_stall(_flat_config(sells="drink"), _meshes(tmp_path))


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


def test_sells_on_cash_machine_rejected(tmp_path):
    # A cash machine paints like a shop but dispenses cash, so it cannot sell.
    with pytest.raises(LoadError, match="cash_machine"):
        build_stall(
            _config(ride_type="cash_machine", sells="drink"), _meshes(tmp_path)
        )


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
