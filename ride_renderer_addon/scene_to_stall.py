"""
Read the Blender scene into the ride generator's config + meshes.
"""

from __future__ import annotations

import math

import numpy as np
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


def _flat_ride_animation(context, scene, objects) -> tuple[list[Mesh], list[list[dict]]]:
    """Sample the scene's keyframed spin into the ride's rotation frames.

    This is the Blender-animator path for moving rides: the author keyframes one
    seamless loop of the motion across the scene's frame range (a full turn for the
    carousel and twist, one gondola-spacing for the ferris wheel), and this samples
    ``FLAT_RIDE_SPECS[type].frames`` evenly-spaced structure poses across it. The
    range is treated cyclically (end-exclusive) so the seam pose -- where the loop
    wraps back to the start -- is not duplicated.

    For the single-direction symmetric rides the structure ring is only one
    symmetry period of the turn: the engine loops it ``structure_loops_per_turn``
    times per revolution (twist 9, carousel 4) while the rider ring sweeps the full
    turn, so the structure must rotate at the riders' rate. We therefore sample the
    structure poses across only the first ``1 / structure_loops_per_turn`` of the
    keyframed loop -- a full turn baked into all ``n`` structure frames would spin
    the structure that many times too fast relative to its riders.

    Geometry is extracted once at the rest frame (the parts spin rigidly); each
    pose then records every part's rotation relative to rest, exactly the
    multi-frame model the core renders frame by frame and the engine cycles to
    animate the ride.
    """
    ss = scene.vgr_stall
    spec = FLAT_RIDE_SPECS[ss.stall_type]
    n = spec.frames
    loops = spec.structure_loops_per_turn
    f_start, f_end = scene.frame_start, scene.frame_end
    if f_end <= f_start:
        sampled = [f_start] * n
    else:
        period = f_end - f_start + 1
        sampled = [f_start + round(i * period / (n * loops)) % period for i in range(n)]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    poses: list[list[dict]] = [[] for _ in sampled]
    try:
        # Rest pass: extract each part's mesh once and cache its rest rotation,
        # so later poses carry only the rotation relative to rest.
        scene.frame_set(sampled[0])
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in objects:
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


_SWING_BLOCKS = 19  # FLAT_RIDE_SPECS["swinging_ship"].frames


def _swing_scalars(orientations: list[list[float]]) -> list[float]:
    """Per-sample signed swing angle: the horizontal orientation component (Z or
    X -- indices 1/2 of the renderer's [Y, Z, X] triple, never the vertical yaw)
    that varies most across the keyframed swing."""
    axis, widest = 1, -1.0
    for candidate in (1, 2):
        vals = [o[candidate] for o in orientations]
        spread = max(vals) - min(vals)
        if spread > widest:
            axis, widest = candidate, spread
    return [o[axis] for o in orientations]


def _swing_block_targets(amplitude: float) -> list[float]:
    """The 19 swing-block angles in SwingingShip.cpp image order: block 0 upright,
    blocks 1-9 one lean ramp, blocks 10-18 the other."""
    targets = [0.0]
    targets += [amplitude * r / 9 for r in range(1, 10)]
    targets += [-amplitude * r / 9 for r in range(1, 10)]
    return targets


def _swinging_ship_animation(context, scene, objects) -> tuple[list[Mesh], list[list[dict]]]:
    """Sample a keyframed swing and remap it into the 19 swing-block poses.

    Unlike a steady spin (advanced +1 per tick, so sprite order == keyframe time
    order), the swinging ship stores its sprites in swing-block order: block 0
    upright, then a lean ramp each way. So the author just keyframes a natural
    back-and-forth swing; we sample it densely, measure each pose's swing angle
    (the dominant horizontal rotation), take the amplitude reached, and slot the
    sampled pose nearest each block's target angle into the engine's order.
    """
    f_start, f_end = scene.frame_start, scene.frame_end
    dense = list(range(f_start, f_end + 1)) if f_end > f_start else [f_start]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    samples: list[tuple[list[float], list[dict]]] = []  # (first part's orientation, full pose)
    try:
        scene.frame_set(dense[0])
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in objects:
            mesh = _extract(obj, dg)
            if mesh is None:
                continue
            idx = len(meshes)
            meshes.append(mesh)
            rigid.append((obj, idx, rest_rotation_inverse(obj.evaluated_get(dg).matrix_world)))
        for frame in dense:
            scene.frame_set(frame)
            dg = context.evaluated_depsgraph_get()
            entries: list[dict] = []
            first_orient = [0.0, 0.0, 0.0]
            for obj, idx, rest_inv in rigid:
                position, orientation = rigid_pose(obj.evaluated_get(dg).matrix_world, rest_inv)
                if not entries:
                    first_orient = orientation
                entries.append(
                    {"mesh_index": idx, "position": position, "orientation": orientation}
                )
            samples.append((first_orient, entries))
    finally:
        scene.frame_set(orig_frame)

    scalars = _swing_scalars([orient for orient, _ in samples])
    amplitude = max((abs(s) for s in scalars), default=0.0)
    poses: list[list[dict]] = []
    for target in _swing_block_targets(amplitude):
        best = min(range(len(samples)), key=lambda i, t=target: abs(scalars[i] - t))
        poses.append(samples[best][1])
    return meshes, poses


def _rigid_rider_frames(
    context, scene, rider_objs, strip_fracs: list[float]
) -> tuple[list[Mesh], list[list[dict]]]:
    """Sample rider objects rotating rigidly with a full-turn spin (the carousel).

    Each rider rotates with the platform, so its rider-strip pose at strip frame
    ``s`` is the rest pose turned by ``strip_fracs[s]`` of the keyframed loop. We
    extract each rider once at the rest frame (a full turn starts there) and record
    its rigid pose at the scene frame for each strip fraction -- exactly the
    structure spin's sampling, just at the rider ring's finer (and offset) phases.
    """
    f_start, f_end = scene.frame_start, scene.frame_end
    period = (f_end - f_start + 1) if f_end > f_start else 1
    sampled = [f_start + round(frac * period) % period for frac in strip_fracs]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    poses: list[list[dict]] = [[] for _ in sampled]
    try:
        scene.frame_set(f_start)  # rest frame: the spin's zero pose
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in rider_objs:
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


def _fit_orbit_circle(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Algebraic (Kasa) least-squares circle through 2D points -> (cx, cy, radius).

    The ferris wheel's riders orbit the axle, so their sampled positions lie on a
    circle; fitting it lets a keyframe that only sweeps one gondola spacing fill the
    full 128-position orbit. Degenerate (near-stationary) input returns a zero
    radius at the centroid, so the rider simply holds its rest position."""
    pts = np.asarray(points, dtype=np.float64)
    cx = cy = 0.0
    if pts.shape[0] >= 3 and float(pts.std(axis=0).max()) > 1e-6:
        a = np.column_stack([pts[:, 0], pts[:, 1], np.ones(pts.shape[0])])
        b = pts[:, 0] ** 2 + pts[:, 1] ** 2
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
        cx, cy = sol[0] / 2.0, sol[1] / 2.0
        radius = math.sqrt(max(sol[2] + cx * cx + cy * cy, 0.0))
        return cx, cy, radius
    centroid = pts.mean(axis=0) if pts.size else np.zeros(2)
    return float(centroid[0]), float(centroid[1]), 0.0


def _orbit_rider_frames(
    context, scene, rider_objs, frames: int
) -> tuple[list[Mesh], list[list[dict]]]:
    """Sample riders that orbit upright (the ferris wheel's gondolas).

    The riders stay level while their gondola circles the axle, so the only thing
    that varies is position -- a circle. We densely sample each rider's position
    across the keyframe (which need only sweep part of the orbit), fit its circle,
    and emit ``frames`` evenly-spaced upright positions all the way around, starting
    from the rider's rest position in its observed travel direction.
    """
    f_start, f_end = scene.frame_start, scene.frame_end
    dense = list(range(f_start, f_end + 1)) if f_end > f_start else [f_start]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    tracked: list = []  # (idx, [(x, y, z) per dense frame])
    try:
        scene.frame_set(dense[0])
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in rider_objs:
            mesh = _extract(obj, dg)
            if mesh is None:
                continue
            idx = len(meshes)
            meshes.append(mesh)
            rest_inv = rest_rotation_inverse(obj.evaluated_get(dg).matrix_world)
            rigid.append((obj, idx, rest_inv))
            tracked.append((idx, []))
        for frame in dense:
            scene.frame_set(frame)
            dg = context.evaluated_depsgraph_get()
            for (obj, _idx, rest_inv), (_, path) in zip(rigid, tracked, strict=True):
                position, _ = rigid_pose(obj.evaluated_get(dg).matrix_world, rest_inv)
                path.append(position)
    finally:
        scene.frame_set(orig_frame)

    poses: list[list[dict]] = [[] for _ in range(frames)]
    for idx, path in tracked:
        cx, cy, radius = _fit_orbit_circle([(p[0], p[1]) for p in path])
        z = path[0][2]
        theta0 = math.atan2(path[0][1] - cy, path[0][0] - cx)
        theta_end = math.atan2(path[-1][1] - cy, path[-1][0] - cx)
        sweep = ((theta_end - theta0 + math.pi) % (2 * math.pi)) - math.pi
        direction = -1.0 if sweep < 0 else 1.0
        for s in range(frames):
            theta = theta0 + direction * 2.0 * math.pi * s / frames
            poses[s].append(
                {
                    "mesh_index": idx,
                    "position": [
                        round(cx + radius * math.cos(theta), 4),
                        round(cy + radius * math.sin(theta), 4),
                        round(z, 4),
                    ],
                    "orientation": [0.0, 0.0, 0.0],
                }
            )
    return meshes, poses


# Each trailing-rider-ring ride samples its rider as a rigid part of the spin,
# at these fractions of the keyframed loop (the engine's rider-strip phases).
# The ferris wheel is the exception: its riders orbit upright (circle fit).
def _rider_ring_fracs(stall_type: str, n: int) -> list[float]:
    if stall_type == "merry_go_round":
        # One seat's pair on the front-visible arc: ring positions 13..80 of 128.
        return [(s + 13) / 128.0 for s in range(n)]
    if stall_type == "enterprise":
        # 3 animation sub-frames x 16 folded positions, index = animFrame*16 +
        # posIndex; posIndex steps 22.5 deg, animFrame subdivides by 7.5 deg.
        return [((s % 16) * 3 + s // 16) * 7.5 / 360.0 for s in range(n)]
    # twist (216) and space rings (88) are an even sweep of the full turn / tumble.
    return [s / n for s in range(n)]


def _shift_mesh_indices(poses: list[list[dict]], base_index: int) -> None:
    for pose in poses:
        for entry in pose:
            entry["mesh_index"] += base_index


def _rider_ring(
    context, scene, rider_objs, stall_type: str, base_index: int
) -> tuple[list[Mesh], list[list[dict]]] | None:
    """Sample the Rider-role meshes into the ride's trailing rider ring, or None if
    the ride has no ring / the scene marks no riders. ``base_index`` is the mesh
    count already used by the structure, so rider placements index past it."""
    spec = FLAT_RIDE_SPECS[stall_type]
    if not spec.has_rider_ring or not rider_objs:
        return None
    if stall_type == "ferris_wheel":
        # The gondola riders orbit the axle upright (a circle fit), not a rigid spin.
        meshes, poses = _orbit_rider_frames(context, scene, rider_objs, spec.rider_frames)
    else:
        fracs = _rider_ring_fracs(stall_type, spec.rider_frames)
        meshes, poses = _rigid_rider_frames(context, scene, rider_objs, fracs)
    if not meshes:
        return None
    _shift_mesh_indices(poses, base_index)
    return meshes, poses


def _rider_rows(
    context, scene, rider_objs, stall_type: str, base_index: int
) -> tuple[list[Mesh], list[list[list[dict]]]] | None:
    """Sample the Rider-role meshes into the swinging ship's interleaved bench rows.

    Each rider object is one bench row that swings with the ship, so -- like the
    structure -- its keyframed swing is remapped into the engine's 19 swing blocks
    (block 0 upright, then each lean ramp). Rider objects map to sub-slots in name
    order; there must be one per sub-slot. Returns ``(meshes, rows)`` where each row
    is a list of swing-block poses, or None if the scene marks no riders."""
    spec = FLAT_RIDE_SPECS[stall_type]
    if not spec.has_rider_sub_slots or not rider_objs:
        return None
    f_start, f_end = scene.frame_start, scene.frame_end
    dense = list(range(f_start, f_end + 1)) if f_end > f_start else [f_start]

    orig_frame = scene.frame_current
    meshes: list[Mesh] = []
    # Per rider object (sorted to fix the bench order): (idx, [(pos, orient) dense]).
    tracked: list[tuple[int, list[tuple[list[float], list[float]]]]] = []
    try:
        scene.frame_set(dense[0])
        dg = context.evaluated_depsgraph_get()
        rigid: list = []
        for obj in sorted(rider_objs, key=lambda o: o.name):
            mesh = _extract(obj, dg)
            if mesh is None:
                continue
            idx = len(meshes)
            meshes.append(mesh)
            rigid.append((obj, idx, rest_rotation_inverse(obj.evaluated_get(dg).matrix_world)))
            tracked.append((idx, []))
        for frame in dense:
            scene.frame_set(frame)
            dg = context.evaluated_depsgraph_get()
            for (obj, _idx, rest_inv), (_, samples) in zip(rigid, tracked, strict=True):
                samples.append(rigid_pose(obj.evaluated_get(dg).matrix_world, rest_inv))
    finally:
        scene.frame_set(orig_frame)
    if not meshes:
        return None

    rows: list[list[list[dict]]] = []
    for idx, samples in tracked:
        scalars = _swing_scalars([orient for _, orient in samples])
        amplitude = max((abs(s) for s in scalars), default=0.0)
        row: list[list[dict]] = []
        for target in _swing_block_targets(amplitude):
            best = min(range(len(samples)), key=lambda i, t=target: abs(scalars[i] - t))
            position, orientation = samples[best]
            row.append([{"mesh_index": idx + base_index, "position": position,
                         "orientation": orientation}])
        rows.append(row)
    return meshes, rows


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
    rider_frames = None
    rider_rows = None
    if kind is StallKind.FLAT_RIDE:
        spec = FLAT_RIDE_SPECS[ss.stall_type]
        objects = geometry_objects(scene.objects, "vgr_object")
        # Rider-role meshes spin/orbit with the structure but feed separate rider
        # slots; split them off so the structure samples without them and they fill
        # those slots instead of being left blank. Only rides that support riders
        # split them off (the role selector hides Rider otherwise); elsewhere a stray
        # Rider mesh stays plain structure geometry.
        if spec.supports_riders:
            rider_objs = [o for o in objects if o.vgr_object.role == "RIDER"]
            structure_objs = [o for o in objects if o.vgr_object.role != "RIDER"]
        else:
            rider_objs = []
            structure_objs = objects
        # The swinging ship's sprites are in swing-block order, not keyframe-time
        # order, so it samples + remaps the swing rather than evenly sampling a spin.
        if ss.stall_type == "swinging_ship":
            meshes, frames = _swinging_ship_animation(context, scene, structure_objs)
        else:
            meshes, frames = _flat_ride_animation(context, scene, structure_objs)
        # Riders come as a trailing ring or, for the swinging ship, interleaved
        # bench rows.
        if spec.has_rider_sub_slots:
            rows = _rider_rows(context, scene, rider_objs, ss.stall_type, len(meshes))
            if rows is not None:
                rider_meshes, rider_rows = rows
                meshes = meshes + rider_meshes
        else:
            ring = _rider_ring(context, scene, rider_objs, ss.stall_type, len(meshes))
            if ring is not None:
                rider_meshes, rider_frames = ring
                meshes = meshes + rider_meshes
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
        if rider_frames is not None:
            config["rider_animation"] = {"frames": rider_frames}
        if rider_rows is not None:
            config["rider_rows"] = [{"frames": row} for row in rider_rows]
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
