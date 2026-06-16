"""
Build object.json and assemble the stall .parkobj ZIP.
"""

from pathlib import Path
from typing import Any

from openrct2_object_common.export import ProgressFn, export_object, export_to_directory
from openrct2_object_common.objectjson import object_json_header_for, object_strings
from openrct2_object_common.parkobj import write_images_dat_lgx
from openrct2_object_common.preview import open_test_dir, write_combined_preview
from openrct2_x7_renderer.geometry import combine_model_world
from openrct2_x7_renderer.image import write_png
from openrct2_x7_renderer.ray_trace import Context
from openrct2_x7_renderer.types import IndexedImage

from .constants import (
    BUILDING_CAR_ENTRY,
    BUILDING_TYPES_WITH_WAYPOINTS,
    FLAT_RIDE_SPECS,
    LOADING_WAYPOINTS,
    PREVIEW_SLOTS,
    StallKind,
)
from .sprite_renderer import (
    center_preview,
    render_building,
    render_facility,
    render_flat_ride,
    render_shop,
)
from .types import Stall


def _build_car_entry(stall: Stall) -> dict[str, Any]:
    """The building / flat ride's single car entry.

    Building rides never draw the car as a vehicle (the track painter reads
    base_image_id directly); animated flat rides draw the structure through the
    vehicle path and cycle its rotation frames."""
    if stall.kind is StallKind.FLAT_RIDE:
        spec = FLAT_RIDE_SPECS[stall.stall_type]
        car: dict[str, Any] = dict(spec.car)
        car["loadingWaypoints"] = [[list(p) for p in wp] for wp in spec.waypoints]
    else:
        car = dict(BUILDING_CAR_ENTRY)
        if stall.stall_type in BUILDING_TYPES_WITH_WAYPOINTS:
            car["loadingWaypoints"] = [[list(p) for p in wp] for wp in LOADING_WAYPOINTS]
    car["numSeats"] = stall.num_seats
    # The colour window shows the trim/tertiary pickers only when the car
    # opts in; derive that from the remap regions the materials actually use.
    regions = {m.region for mesh in stall.meshes for m in mesh.materials}
    if 2 in regions:
        car["hasAdditionalColour1"] = True
    if 3 in regions:
        car["hasAdditionalColour2"] = True
    return car


def build_stall_json(stall: Stall) -> dict[str, Any]:
    out = object_json_header_for(stall, "ride")
    # Building rides and animated flat rides are "gentle" rides that carry their
    # own car entry; shops and facilities are "stall" rides the engine fills in.
    has_car = stall.kind in (StallKind.BUILDING, StallKind.FLAT_RIDE)

    # Shops/facilities are "stall" rides; building rides are all "gentle"; flat
    # rides carry the category from their spec (the carousel/ferris are gentle,
    # the twist/enterprise are thrill).
    if stall.kind is StallKind.FLAT_RIDE:
        category = FLAT_RIDE_SPECS[stall.stall_type].category
    elif has_car:
        category = "gentle"
    else:
        category = "stall"

    properties: dict[str, Any] = {
        "type": stall.stall_type,
        "category": category,
        "clearance": stall.clearance,
    }
    if has_car:
        # The whole-structure sprites overflow the build-menu tab at full size.
        properties["tabScale"] = 0.5
        # Buildings always shelter guests; flat rides declare it per type.
        if stall.kind is StallKind.FLAT_RIDE:
            spec = FLAT_RIDE_SPECS[stall.stall_type]
            if spec.has_shelter:
                properties["hasShelter"] = True
            if spec.rotation_mode is not None:
                properties["rotationMode"] = spec.rotation_mode
        else:
            properties["hasShelter"] = True
    if stall.sells:
        properties["sells"] = stall.sells[0] if len(stall.sells) == 1 else list(stall.sells)
    if stall.disable_painting:
        properties["disablePainting"] = True
    properties["carsPerFlatRide"] = 1
    # The engine synthesizes the whole car entry for shop/facility ride types,
    # so only the car-bearing rides emit a "cars" block.
    if has_car:
        properties["cars"] = _build_car_entry(stall)
    properties["carColours"] = [[list(preset)] for preset in stall.car_colours]
    if stall.build_menu_priority:
        properties["buildMenuPriority"] = stall.build_menu_priority
    out["properties"] = properties

    out["strings"] = object_strings(
        stall.name,
        description=stall.description,
        capacity=f"{stall.num_seats} guests" if has_car else None,
    )
    return out


def _render_views(
    stall: Stall, context: Context, progress: ProgressFn | None = None
) -> list[IndexedImage]:
    """Render the stall's view sprites in the engine's image order."""
    if stall.kind is StallKind.FLAT_RIDE:
        # The flat ride is posed per frame (its authored spin), so it renders
        # straight from the multi-frame model rather than a single baked mesh.
        return render_flat_ride(
            context, stall.meshes, stall.model, stall.stall_type, progress
        )
    combined = combine_model_world(stall.meshes, stall.model)
    if stall.kind is StallKind.FACILITY:
        door = (
            combine_model_world(stall.meshes, stall.door_model)
            if stall.facility_door_split
            else None
        )
        return render_facility(context, combined, door, stall.units_per_tile, progress)
    if stall.kind is StallKind.BUILDING:
        return render_building(
            context, combined, stall.stall_type, stall.units_per_tile, progress
        )
    return render_shop(context, combined, stall.units_per_tile, progress)


def _preview_image(stall: Stall, views: list[IndexedImage]) -> IndexedImage:
    """The user-supplied preview PNG, or the direction-0 view sprite re-anchored
    to centre in the ride window's preview box."""
    if stall.preview is not None:
        return stall.preview
    # For facilities image 2 is the direction-0 full building (image 0 is the
    # direction-2 doorway strip); for shops image 0 is direction 0.
    front = views[2] if stall.kind is StallKind.FACILITY else views[0]
    return center_preview(front)


def _render_sprites(
    stall: Stall,
    context: Context,
    object_dir: Path,
    progress: ProgressFn | None = None,
) -> list[str]:
    views = _render_views(stall, context, progress)
    images = [_preview_image(stall, views)] * PREVIEW_SLOTS + views
    return write_images_dat_lgx(images, object_dir)


def export_stall_to(
    stall: Stall,
    context: Context,
    parkobj_path: Path | str,
    work_dir: Path | str,
    skip_render: bool = False,
    progress: ProgressFn | None = None,
) -> None:
    """Render the sprites (or reuse a previous render) and zip object.json +
    images.dat into the parkobj."""
    export_object(
        stall, context, build_stall_json(stall), _render_sprites, parkobj_path, work_dir,
        skip_render=skip_render, progress=progress,
    )


def export_stall(
    stall: Stall, context: Context, output_directory: Path | str, skip_render: bool = False
) -> None:
    export_to_directory(
        export_stall_to, stall, context, output_directory, stall.id, skip_render=skip_render
    )


def export_stall_test(stall: Stall, context: Context, test_dir: Path | str = "test") -> None:
    """Per-view renders for fast iteration (plus the facility door/body split)."""
    test_dir = open_test_dir(test_dir)
    # Drop the trailing blank animation overlays (haunted house ghosts).
    views = _render_views(stall, context)[: stall.num_view_sprites]
    for i, img in enumerate(views):
        write_png(img, test_dir / f"stall_{i}.png")
    if stall.kind is StallKind.FACILITY and stall.facility_door_split:
        door = combine_model_world(stall.meshes, stall.door_model)
        note = f"door {door.faces.shape[0]} faces (strip cut at the door mesh's screen extent)"
        (test_dir / "door_split.txt").write_text(note + "\n")
    write_png(_preview_image(stall, views), test_dir / "preview.png")
    write_combined_preview(views, test_dir)
