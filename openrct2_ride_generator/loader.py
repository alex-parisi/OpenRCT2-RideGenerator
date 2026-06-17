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
    load_single_frame_model,
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
    FLAT_RIDE_SPECS,
    MAX_SELLS,
    SHOP_ITEMS,
    SHOP_SELL_TYPES,
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


def _load_flat_ride_model(root: dict[str, Any], num_meshes: int, ride_type: str) -> Model:
    """Parse an animated flat ride's spin into a multi-frame Model.

    The add-on (or this config's ``animation.frames`` list) supplies one pose --
    a full ``model`` placement list -- per rotation frame. Most rides author one
    full revolution, but the single-direction symmetric rides span only one
    symmetry period (the engine loops their ring ``structure_loops_per_turn`` times
    per turn: the carousel's 32 poses cover 90 degrees, the twist's 24 cover 40),
    so the structure rotates at the riders' rate. Each placement carries one
    :class:`MeshFrame` per pose, exactly the shape :func:`combine_model_world`
    bakes when asked for a given frame. The frame count must match the ride's
    declared rotation-frame count so the rendered ring lines up with the
    engine's ``rotationFrameMask``.
    """
    anim = root.get("animation")
    if not isinstance(anim, dict):
        raise LoadError(f'A "{ride_type}" flat ride needs an "animation" object')
    frames_value = anim.get("frames")
    if not isinstance(frames_value, list) or not frames_value:
        raise LoadError('Property "animation.frames" not found or is not a non-empty array')
    expected = FLAT_RIDE_SPECS[ride_type].frames
    if len(frames_value) != expected:
        raise LoadError(
            f'A "{ride_type}" needs exactly {expected} animation frames, '
            f"got {len(frames_value)}"
        )
    poses = [load_single_frame_model(pose, num_meshes) for pose in frames_value]
    n = len(poses[0].meshes)
    for pose in poses:
        if len(pose.meshes) != n:
            raise LoadError("All animation frames must list the same number of model entries")
    meshes_out = [[poses[g].meshes[i][0] for g in range(len(poses))] for i in range(n)]
    return Model(meshes=meshes_out)


def _load_rider_model(root: dict[str, Any], num_meshes: int, ride_type: str) -> Model:
    """Parse an animated flat ride's optional rider ring into a multi-frame Model.

    The ``rider_animation.frames`` list mirrors ``animation.frames`` -- one full
    ``model`` placement list per rider-strip frame -- but poses the seated
    rider-pair the engine draws over the structure (the carousel's 68 orbit poses,
    the ferris wheel's 128). Absent, the rider slots stay blank. The frame count
    must match the ride's declared rider strip so the rendered ring lines up with
    the engine's per-seat image offsets."""
    spec = FLAT_RIDE_SPECS[ride_type]
    anim = root.get("rider_animation")
    if anim is None:
        return Model()
    if not spec.has_rider_ring:
        raise LoadError(f'A "{ride_type}" flat ride has no rider ring (remove "rider_animation")')
    if not isinstance(anim, dict):
        raise LoadError('Property "rider_animation" must be an object with a "frames" array')
    frames_value = anim.get("frames")
    if not isinstance(frames_value, list) or not frames_value:
        raise LoadError(
            'Property "rider_animation.frames" not found or is not a non-empty array'
        )
    if len(frames_value) != spec.rider_frames:
        raise LoadError(
            f'A "{ride_type}" rider ring needs exactly {spec.rider_frames} frames, '
            f"got {len(frames_value)}"
        )
    poses = [load_single_frame_model(pose, num_meshes) for pose in frames_value]
    n = len(poses[0].meshes)
    for pose in poses:
        if len(pose.meshes) != n:
            raise LoadError(
                "All rider_animation frames must list the same number of model entries"
            )
    meshes_out = [[poses[g].meshes[i][0] for g in range(len(poses))] for i in range(n)]
    return Model(meshes=meshes_out)


def _load_rider_rows(root: dict[str, Any], num_meshes: int, ride_type: str) -> list[Model]:
    """Parse an interleaved-rider ride's optional bench rows (the swinging ship).

    Unlike the trailing rider ring, the swinging ship draws its riders in the
    sub-slots after each ship sprite -- one per bench row -- so the object supplies
    one rider sub-model per sub-slot under ``rider_rows`` (each a multi-frame model
    over the ship's swing blocks, like ``animation.frames``). Absent, the sub-slots
    stay blank. There must be exactly ``blank_sub_slots`` rows, each with the ride's
    structure frame count."""
    spec = FLAT_RIDE_SPECS[ride_type]
    rows = root.get("rider_rows")
    if rows is None:
        return []
    if not spec.has_rider_sub_slots:
        raise LoadError(f'A "{ride_type}" flat ride has no rider rows (remove "rider_rows")')
    if not isinstance(rows, list):
        raise LoadError('Property "rider_rows" must be a list of bench rows')
    if len(rows) != spec.blank_sub_slots:
        raise LoadError(
            f'A "{ride_type}" needs exactly {spec.blank_sub_slots} rider_rows, got {len(rows)}'
        )
    models: list[Model] = []
    for row in rows:
        if not isinstance(row, dict):
            raise LoadError('Each "rider_rows" entry must be an object with a "frames" array')
        frames_value = row.get("frames")
        if not isinstance(frames_value, list) or len(frames_value) != spec.frames:
            raise LoadError(
                f'Each "rider_rows" entry needs exactly {spec.frames} frames'
            )
        poses = [load_single_frame_model(pose, num_meshes) for pose in frames_value]
        n = len(poses[0].meshes)
        for pose in poses:
            if len(pose.meshes) != n:
                raise LoadError("All rider_rows frames must list the same number of model entries")
        models.append(
            Model(meshes=[[poses[g].meshes[i][0] for g in range(len(poses))] for i in range(n)])
        )
    return models


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

    if sells and ride_type not in SHOP_SELL_TYPES:
        kind = STALL_TYPES[ride_type]
        noun = {
            StallKind.FACILITY: "facility",
            StallKind.BUILDING: "building ride",
        }.get(kind, "ride")
        raise LoadError(f'A "{ride_type}" {noun} cannot have a "sells" property')
    if not sells and ride_type in ("food_stall", "drink_stall"):
        log.warning("%s with no sells items: the stall will sell nothing", ride_type)
    return sells


def _has_car(ride_type: str) -> bool:
    """Ride kinds that carry an explicit car entry (= capacity via numSeats):
    the 3x3 building rides and the animated flat rides."""
    return STALL_TYPES[ride_type] in (StallKind.BUILDING, StallKind.FLAT_RIDE)


def _load_seats(root: dict[str, Any], ride_type: str) -> int:
    """Building / flat rides only: the car's numSeats (= ride capacity)."""
    if "seats" in root and not _has_car(ride_type):
        raise LoadError(f'A "{ride_type}" ride cannot have a "seats" property')
    default = DEFAULT_NUM_SEATS.get(ride_type, 0)
    seats = optional_int(root, "seats", default)
    if _has_car(ride_type) and not 1 <= seats <= 255:
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
    if obj.kind is StallKind.FLAT_RIDE:
        # Animated flat rides are posed by their `animation.frames` spin, not a
        # static `model`; the door split never applies.
        if "model" in root:
            raise LoadError(
                f'A "{obj.stall_type}" flat ride is posed by "animation.frames", '
                'not a static "model"'
            )
        obj.model = _load_flat_ride_model(root, len(obj.meshes), obj.stall_type)
        obj.rider_model = _load_rider_model(root, len(obj.meshes), obj.stall_type)
        obj.rider_sub_models = _load_rider_rows(root, len(obj.meshes), obj.stall_type)
        obj.door_model = Model()
    else:
        if "rider_animation" in root:
            raise LoadError(
                f'A "{obj.stall_type}" ride has no rider ring (remove "rider_animation")'
            )
        if "rider_rows" in root:
            raise LoadError(
                f'A "{obj.stall_type}" ride has no rider rows (remove "rider_rows")'
            )
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
