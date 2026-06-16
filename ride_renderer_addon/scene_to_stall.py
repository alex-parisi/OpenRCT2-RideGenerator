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
    rest_rotation_inverse,
    rigid_pose,
)
from openrct2_ride_generator.constants import (
    FLAT_RIDE_SPECS,
    SHOP_SELL_TYPES,
    STALL_TYPES,
    StallKind,
)
from openrct2_ride_generator.loader import build_stall
from openrct2_ride_generator.types import Stall
from openrct2_x7_renderer.mesh import Mesh

# Owns this build's baked-texture map + the scene extractor (material_base +
# apply_settings_texture); refreshed by build_stall_from_scene before extraction.
_extractor = MaterialExtractor("vgr_material", ghost_attr="vgr_object")
_extract = _extractor.extract


def _sells(ss) -> list[str]:
    return [item for item in (ss.sells_1, ss.sells_2) if item != "NONE"]


def _static_model(scene, depsgraph, kind: StallKind) -> tuple[list[Mesh], list[dict]]:
    """Extract the single-pose model: every geometry part at the current frame."""
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
    return meshes, model


def _flat_ride_animation(context, scene) -> tuple[list[Mesh], list[list[dict]]]:
    """Sample the scene's keyframed spin into the ride's rotation frames.

    This is the Blender-animator path for moving rides: the author keyframes one
    seamless loop of the spin across the scene's frame range (a full turn for the
    carousel, one gondola-spacing for the ferris wheel), and this samples
    ``FLAT_RIDE_SPECS[type].frames`` evenly-spaced poses across it. The range is
    treated cyclically (end-exclusive) so the seam pose -- where the loop wraps
    back to the start -- is not duplicated. Geometry is extracted once at the
    rest frame (the parts spin rigidly); each pose then records every part's
    rotation relative to rest, exactly the multi-frame model the core renders
    frame by frame and the engine cycles to animate the ride.
    """
    ss = scene.vgr_stall
    n = FLAT_RIDE_SPECS[ss.stall_type].frames
    f_start, f_end = scene.frame_start, scene.frame_end
    if f_end <= f_start:
        sampled = [f_start] * n
    else:
        period = f_end - f_start + 1
        sampled = [f_start + round(i * period / n) % period for i in range(n)]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    poses: list[list[dict]] = [[] for _ in sampled]
    try:
        # Rest pass: extract each part's mesh once and cache its rest rotation,
        # so later poses carry only the rotation relative to rest.
        scene.frame_set(sampled[0])
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in geometry_objects(scene.objects, "vgr_object"):
            mesh = _extract(obj, dg)
            if mesh is None:
                continue
            idx = len(meshes)
            meshes.append(mesh)
            rigid.append((obj, idx, rest_rotation_inverse(obj.evaluated_get(dg).matrix_world)))
        for fi, frame in enumerate(sampled):
            scene.frame_set(frame)
            dg = context.evaluated_depsgraph_get()
            for obj, idx, rest_inv in rigid:
                position, orientation = rigid_pose(obj.evaluated_get(dg).matrix_world, rest_inv)
                poses[fi].append(
                    {"mesh_index": idx, "position": position, "orientation": orientation}
                )
    finally:
        scene.frame_set(orig_frame)
    return meshes, poses


def build_stall_from_scene(context) -> Stall:
    """Read the scene's settings + geometry and build a validated Stall."""
    scene = context.scene
    ss = scene.vgr_stall
    depsgraph = context.evaluated_depsgraph_get()
    kind = STALL_TYPES[ss.stall_type]

    # Bake any procedural-node materials to textures up front (main thread, Cycles),
    # then feed them into extraction via the extractor. Refreshed each call.
    _extractor.bake(context, geometry_objects(scene.objects, "vgr_object"))

    # Animated flat rides are posed by their keyframed spin; every other kind is
    # a single static pose.
    if kind is StallKind.FLAT_RIDE:
        meshes, frames = _flat_ride_animation(context, scene)
        model = None
    else:
        meshes, model = _static_model(scene, depsgraph, kind)
        frames = None

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
    }
    if frames is not None:
        config["animation"] = {"frames": frames}
    else:
        config["model"] = model
    # The sells/seats UI fields keep stale values when the type changes, so
    # only the fields the chosen kind accepts are forwarded.
    if ss.stall_type in SHOP_SELL_TYPES:
        config["sells"] = _sells(ss)
    if kind in (StallKind.BUILDING, StallKind.FLAT_RIDE) and ss.seats > 0:
        config["seats"] = int(ss.seats)
    if ss.clearance > 0:
        config["clearance"] = int(ss.clearance)
    if ss.colour_presets:
        config["car_colours"] = [
            [p.main, p.additional_1, p.additional_2] for p in ss.colour_presets
        ]
    return build_stall(config, meshes)
