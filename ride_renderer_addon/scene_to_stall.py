"""
Read the Blender scene into the ride generator's config + meshes.
"""

from __future__ import annotations

from openrct2_object_common.blender.mesh_extract import (
    MaterialExtractor,
    SceneError,
    geometry_objects,
    object_position,
    parse_authors,
)
from openrct2_ride_generator.constants import STALL_TYPES, StallKind
from openrct2_ride_generator.loader import build_stall
from openrct2_ride_generator.types import Stall
from openrct2_x7_renderer.mesh import Mesh

# Owns this build's baked-texture map + the scene extractor (material_base +
# apply_settings_texture); refreshed by build_stall_from_scene before extraction.
_extractor = MaterialExtractor("vgr_material", ghost_attr="vgr_object")
_extract = _extractor.extract


def _sells(ss) -> list[str]:
    return [item for item in (ss.sells_1, ss.sells_2) if item != "NONE"]


def build_stall_from_scene(context) -> Stall:
    """Read the scene's settings + geometry and build a validated Stall."""
    scene = context.scene
    ss = scene.vgr_stall
    depsgraph = context.evaluated_depsgraph_get()
    kind = STALL_TYPES[ss.stall_type]

    # Bake any procedural-node materials to textures up front (main thread, Cycles),
    # then feed them into extraction via the extractor. Refreshed each call.
    _extractor.bake(context, geometry_objects(scene.objects, "vgr_object"))

    meshes: list[Mesh] = []
    model: list[dict] = []
    for obj in geometry_objects(scene.objects, "vgr_object"):
        mesh = _extract(obj, depsgraph)
        if mesh is None:
            continue
        idx = len(meshes)
        meshes.append(mesh)
        entry: dict = {
            "mesh_index": idx,
            "position": object_position(obj),
            "orientation": [0, 0, 0],
        }
        # The Door role only means something to facilities; like the sells/
        # seats fields, it is not forwarded for other kinds (loader rejects it).
        if kind is StallKind.FACILITY and obj.vgr_object.role == "DOOR":
            entry["door"] = True
        model.append(entry)

    if not meshes:
        raise SceneError(
            "No geometry found. Add a mesh and set its role to 'Geometry' "
            "in the OpenRCT2 Ride panel."
        )

    authors = parse_authors(ss.authors)

    config: dict = {
        "object_type": "ride",
        "id": ss.id,
        "name": ss.name,
        "description": ss.description,
        "authors": authors,
        "version": ss.version,
        "units_per_tile": float(ss.units_per_tile),
        "ride_type": ss.stall_type,
        "disable_painting": ss.disable_painting,
        "facility_door_split": ss.facility_door_split,
        "model": model,
    }
    # The sells/seats UI fields keep stale values when the type changes, so
    # only the fields the chosen kind accepts are forwarded.
    if kind is StallKind.SHOP:
        config["sells"] = _sells(ss)
    if kind is StallKind.BUILDING and ss.seats > 0:
        config["seats"] = int(ss.seats)
    if ss.clearance > 0:
        config["clearance"] = int(ss.clearance)
    if ss.colour_presets:
        config["car_colours"] = [
            [p.main, p.additional_1, p.additional_2] for p in ss.colour_presets
        ]
    return build_stall(config, meshes)
