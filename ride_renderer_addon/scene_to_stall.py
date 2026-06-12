"""
Read the Blender scene into the ride generator's config + meshes.
"""

from __future__ import annotations

import os

import bpy
from openrct2_object_common.blender.mesh_extract import (
    SceneError,
    extract_mesh,
    material_base,
    object_position,
)
from openrct2_ride_generator.constants import STALL_TYPES, StallKind
from openrct2_ride_generator.loader import build_stall
from openrct2_ride_generator.types import Stall
from openrct2_x7_renderer.constants import MaterialFlag
from openrct2_x7_renderer.mesh import Material, Mesh, load_texture

_REGION_MAP = {
    "NONE": (0, 0),
    "REMAP1": (MaterialFlag.IS_REMAPPABLE, 1),
    "REMAP2": (MaterialFlag.IS_REMAPPABLE, 2),
    "REMAP3": (MaterialFlag.IS_REMAPPABLE, 3),
    "GREYSCALE": (0, 4),
    "PEEP": (0, 5),
}


def _material_from_bpy(bmat) -> Material:
    m, s = material_base(bmat, prop_attr="vgr_material", region_map=_REGION_MAP)
    if s is None:
        return m
    if s.texture is not None:
        path = bpy.path.abspath(s.texture.filepath_from_user() or s.texture.filepath)
        if path and os.path.exists(path):
            m.texture = load_texture(path)
            m.flags |= MaterialFlag.HAS_TEXTURE
    return m


def _extract(obj, depsgraph) -> Mesh | None:
    mesh = extract_mesh(obj, depsgraph, _material_from_bpy)
    # A per-object "Ghost" toggle marks the whole mesh's geometry as ghost so
    # the renderer traces through it.
    if mesh is not None and obj.vgr_object.is_ghost:
        for material in mesh.materials:
            material.is_ghost = True
    return mesh


def _geometry_objects(objects) -> list:
    """Mesh objects that are part of the model (role != IGNORE)."""
    return [
        obj
        for obj in objects
        if obj.type == "MESH" and obj.vgr_object.role != "IGNORE"
    ]


def _sells(ss) -> list[str]:
    return [item for item in (ss.sells_1, ss.sells_2) if item != "NONE"]


def build_stall_from_scene(context) -> Stall:
    """Read the scene's settings + geometry and build a validated Stall."""
    scene = context.scene
    ss = scene.vgr_stall
    depsgraph = context.evaluated_depsgraph_get()

    meshes: list[Mesh] = []
    model: list[dict] = []
    for obj in _geometry_objects(scene.objects):
        mesh = _extract(obj, depsgraph)
        if mesh is None:
            continue
        idx = len(meshes)
        meshes.append(mesh)
        model.append({
            "mesh_index": idx,
            "position": object_position(obj),
            "orientation": [0, 0, 0],
        })

    if not meshes:
        raise SceneError(
            "No geometry found. Add a mesh and set its role to 'Geometry' "
            "in the OpenRCT2 Ride panel."
        )

    authors = [a.strip() for a in ss.authors.split(",") if a.strip()]

    kind = STALL_TYPES[ss.stall_type]
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
