"""
Load a stall config (JSON or YAML) into a Stall dataclass.
"""

import logging
from pathlib import Path
from typing import Any

from openrct2_object_common.config import (
    LoadError,
    as_array_or_wrap,
    load_meshes,
    load_preview,
    optional_bool,
    optional_int,
    optional_number,
    optional_string,
    optional_string_list,
    parse_config,
    read_vector3,
    require_string,
)
from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.mesh import Mesh
from openrct2_x7_renderer.types import IndexedImage, MeshFrame, Model

from .constants import (
    COLOR_NAMES,
    DEFAULT_CLEARANCE,
    DEFAULT_NUM_SEATS,
    MAX_SELLS,
    SHOP_ITEMS,
    STALL_TYPES,
    StallKind,
)
from .types import Stall

log = logging.getLogger(__name__)


def _load_units_per_tile(root: dict[str, Any]) -> float:
    """Render scale: OBJ units per tile. Defaults to RCT2's real-world tile."""
    upt = optional_number(root, "units_per_tile", TILE_SIZE)
    if upt <= 0.0:
        raise LoadError('Property "units_per_tile" must be greater than 0')
    return upt


def _load_identity(obj: Stall, root: dict[str, Any], preview: IndexedImage | None) -> None:
    """Populate the identity + render-scale fields."""
    obj.id = require_string(root, "id")
    obj.original_id = optional_string(root, "original_id")
    obj.name = require_string(root, "name")
    obj.description = require_string(root, "description")
    obj.authors = optional_string_list(root, "authors")
    v_str = optional_string(root, "version")
    if v_str:
        obj.version = v_str
    obj.preview = preview
    obj.units_per_tile = _load_units_per_tile(root)


def _load_model(value: Any, num_meshes: int) -> Model:
    """Parse the single-frame model placement list into a Model."""
    if value is None:
        raise LoadError('Property "model" not found')
    arr = as_array_or_wrap(value)
    meshes_out: list[list[MeshFrame]] = []
    for elem in arr:
        if not isinstance(elem, dict):
            raise LoadError('Property "model" is not an object')

        mi = elem.get("mesh_index")
        if not isinstance(mi, int) or isinstance(mi, bool):
            raise LoadError('Property "mesh_index" not found or is not an integer')
        if mi >= num_meshes or mi < -1:
            raise LoadError(f"Mesh index {mi} is out of bounds")

        kwargs: dict[str, Any] = {"mesh_index": int(mi)}
        for key in ("position", "orientation"):
            prop = elem.get(key)
            if prop is not None:
                kwargs[key] = read_vector3(prop)

        meshes_out.append([MeshFrame(**kwargs)])
    return Model(meshes=meshes_out)


def _load_ride_type(root: dict[str, Any]) -> str:
    ride_type = require_string(root, "ride_type")
    if ride_type not in STALL_TYPES:
        raise LoadError(
            f'Unrecognized ride_type "{ride_type}" (expected one of '
            f"{sorted(STALL_TYPES)})"
        )
    return ride_type


def _load_sells(root: dict[str, Any], ride_type: str) -> list[str]:
    value = root.get("sells")
    if value is None:
        sells: list[str] = []
    else:
        sells = []
        for item in as_array_or_wrap(value):
            if not isinstance(item, str):
                raise LoadError('Property "sells" must be a string or list of strings')
            if item not in SHOP_ITEMS:
                raise LoadError(
                    f'Unrecognized shop item "{item}" (expected one of {sorted(SHOP_ITEMS)})'
                )
            sells.append(item)
        if len(sells) > MAX_SELLS:
            raise LoadError(f'Property "sells" lists {len(sells)} items (max {MAX_SELLS})')

    kind = STALL_TYPES[ride_type]
    if sells and kind is not StallKind.SHOP:
        noun = "facility" if kind is StallKind.FACILITY else "building ride"
        raise LoadError(f'A "{ride_type}" {noun} cannot have a "sells" property')
    if not sells and ride_type in ("food_stall", "drink_stall"):
        log.warning("%s with no sells items: the stall will sell nothing", ride_type)
    return sells


def _load_seats(root: dict[str, Any], ride_type: str) -> int:
    """Building rides only: the car's numSeats (= ride capacity)."""
    default = DEFAULT_NUM_SEATS.get(ride_type, 0)
    seats = optional_int(root, "seats", default)
    if seats != default and STALL_TYPES[ride_type] is not StallKind.BUILDING:
        raise LoadError(f'A "{ride_type}" ride cannot have a "seats" property')
    if STALL_TYPES[ride_type] is StallKind.BUILDING and not 1 <= seats <= 255:
        raise LoadError(f'Property "seats" must be 1-255, got {seats}')
    return seats


def _load_clearance(root: dict[str, Any], ride_type: str) -> int:
    clearance = optional_int(root, "clearance", DEFAULT_CLEARANCE[ride_type])
    if not 1 <= clearance <= 255:
        raise LoadError(f'Property "clearance" must be 1-255, got {clearance}')
    return clearance


def _load_car_colours(root: dict[str, Any]) -> list[list[str]]:
    value = root.get("car_colours")
    if value is None:
        return [["black", "black", "black"]]
    if not isinstance(value, list) or len(value) == 0:
        raise LoadError('Property "car_colours" is not a non-empty array')
    presets: list[list[str]] = []
    for preset in value:
        if not isinstance(preset, list) or len(preset) != 3:
            raise LoadError(
                'Each "car_colours" preset must be a [main, additional1, additional2] triple'
            )
        for name in preset:
            if name not in COLOR_NAMES:
                raise LoadError(f'Unrecognized colour "{name}"')
        presets.append([str(name) for name in preset])
    return presets


def build_stall(
    config: dict[str, Any], meshes: list[Mesh], preview: IndexedImage | None = None
) -> Stall:
    """Build a Stall from a parsed config dict + in-memory meshes."""
    root = config
    obj = Stall()
    _load_identity(obj, root, preview)

    obj.stall_type = _load_ride_type(root)
    obj.sells = _load_sells(root, obj.stall_type)
    obj.clearance = _load_clearance(root, obj.stall_type)
    obj.num_seats = _load_seats(root, obj.stall_type)
    obj.disable_painting = optional_bool(root, "disable_painting", True)
    obj.car_colours = _load_car_colours(root)
    obj.build_menu_priority = optional_int(root, "build_menu_priority", 0)
    obj.facility_door_split = optional_bool(root, "facility_door_split", True)

    obj.meshes = list(meshes)
    obj.model = _load_model(root.get("model"), len(obj.meshes))
    return obj


def _config_dir(json_path: Path | str) -> Path:
    """The directory containing the config file; relative `meshes` / `preview`
    paths resolve against it."""
    return Path(json_path).parent


def load_stall(json_path: Path | str) -> Stall:
    """Parse a config file, load its meshes + preview, build a Stall."""
    root = parse_config(json_path)
    base = _config_dir(json_path)
    return build_stall(root, load_meshes(root, base), load_preview(root, base))


def object_type_of(config: dict[str, Any]) -> str:
    """Read the object type, defaulting to ride (the only v1 kind; flat rides
    slot in beside it later)."""
    t = optional_string(config, "object_type", "ride")
    if t != "ride":
        raise LoadError(f'Unrecognized object_type "{t}"')
    return t
