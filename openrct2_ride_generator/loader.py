"""
Load a stall config (JSON or YAML) into a Stall dataclass.
"""

import logging
from pathlib import Path
from typing import Any

from openrct2_object_common.config import (
    LoadError,
    as_array_or_wrap,
    optional_bool,
    optional_int,
    require_string,
)
from openrct2_object_common.loading import (
    apply_identity,
    load_colour_presets,
    load_object,
    parse_single_frame_model,
    require_choice,
)
from openrct2_object_common.loading import object_type_of as _common_object_type_of
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


def _load_identity(obj: Stall, root: dict[str, Any], preview: IndexedImage | None) -> None:
    """Populate the identity + render-scale fields.

    The shared id/name/authors/version/units_per_tile parse lives in Common
    (:func:`openrct2_object_common.loading.apply_identity`); the stall's
    description and preview (no blank fallback) stay here.
    """
    apply_identity(obj, root)
    obj.description = require_string(root, "description")
    obj.preview = preview


def _load_model(value: Any, num_meshes: int) -> tuple[Model, Model]:
    """Parse the single-frame model placement list into (model, door_model):
    all placements, plus the `door: true` subset (the facility doorway).

    The door subset references the same per-placement frame objects as the full
    model, so a doorway placement is shared between the two by identity."""
    meshes_out: list[list[MeshFrame]] = []
    door_out: list[list[MeshFrame]] = []
    for frame, elem in parse_single_frame_model(value, num_meshes):
        meshes_out.append(frame)
        if optional_bool(elem, "door", False):
            door_out.append(frame)
    return Model(meshes=meshes_out), Model(meshes=door_out)


def _load_ride_type(root: dict[str, Any]) -> str:
    return require_choice(
        require_string(root, "ride_type"),
        STALL_TYPES,
        "ride_type",
        expected=sorted(STALL_TYPES),
    )


def _load_sells(root: dict[str, Any], ride_type: str) -> list[str]:
    value = root.get("sells")
    if value is None:
        sells: list[str] = []
    else:
        sells = []
        for item in as_array_or_wrap(value):
            if not isinstance(item, str):
                raise LoadError('Property "sells" must be a string or list of strings')
            sells.append(
                require_choice(item, SHOP_ITEMS, "shop item", expected=sorted(SHOP_ITEMS))
            )
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
    """Each preset is a required [main, additional1, additional2] colour-name
    triple; the shared parse (Common) yields indices, mapped back to names here.
    Defaults to a single all-black preset when absent."""
    return [
        [COLOR_NAMES[idx] for idx in triple]
        for triple in load_colour_presets(
            root.get("car_colours"),
            "car_colours",
            default=[[0, 0, 0]],
            allow_empty=False,
            require_triple=True,
        )
    ]


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
    obj.model, obj.door_model = _load_model(root.get("model"), len(obj.meshes))
    if obj.door_model.meshes and obj.kind is not StallKind.FACILITY:
        raise LoadError(
            f'Only facilities can mark "door" model entries '
            f'(ride_type "{obj.stall_type}")'
        )
    if obj.kind is StallKind.FACILITY and obj.facility_door_split and not obj.door_model.meshes:
        log.warning(
            "facility has no door-marked mesh: rendering without the door split "
            '(mark the doorway placement with "door: true", '
            'or set facility_door_split: false)'
        )
    return obj


def load_stall(json_path: Path | str) -> Stall:
    """Parse a config file, load its meshes + preview, build a Stall."""
    return load_object(json_path, build_stall)


def object_type_of(config: dict[str, Any]) -> str:
    """Read the object type, defaulting to ride (the only v1 kind; flat rides
    slot in beside it later)."""
    return _common_object_type_of(config, ("ride",), default="ride")
