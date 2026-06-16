#!/usr/bin/env python3
"""Regenerate the bundled CLI example meshes (examples/cli/**/*.obj).

These are simple, readable placeholder models authored procedurally from box /
prism / pyramid / cone primitives so the worked examples cover every ride type
without hand-built art. OBJ space matches the renderer convention: +X forward,
+Y up, +Z right; origin at the footprint-base centre; 1 tile = 3.3 units;
material names drive remap classification (Remap1/2/3 are recolourable).

Run from anywhere:  uv run python scripts/gen_example_meshes.py

The merry-go-round's 32-pose spin lives in merry_go_round.yaml's
`animation.frames`; pass --print-spin to re-emit that block (one 360-degree turn
about +Y in `merry_go_round` rotation-frame steps).
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STALL = REPO / "examples" / "cli" / "stall"
BUILD = REPO / "examples" / "cli" / "building"

MERRY_GO_ROUND_FRAMES = 32


class ObjBuilder:
    """Accumulates vertices / normals / per-material face groups, then writes a
    readable .obj with one `usemtl` group per part."""

    def __init__(self, header: str) -> None:
        self.header = header
        self.v: list[tuple[float, float, float]] = []
        self.vn: list[tuple[float, float, float]] = []
        # groups: list of (material, list-of-faces); face = list of (vi, ni)
        self.groups: list[tuple[str, list[list[tuple[int, int]]]]] = []

    def _vi(self, p) -> int:
        self.v.append((round(p[0], 4), round(p[1], 4), round(p[2], 4)))
        return len(self.v)

    def _ni(self, n) -> int:
        ln = math.sqrt(sum(c * c for c in n)) or 1.0
        n = tuple(round(c / ln, 4) for c in n)
        for i, existing in enumerate(self.vn):
            if existing == n:
                return i + 1
        self.vn.append(n)
        return len(self.vn)

    def quad(self, mat, a, b, c, d, normal):
        """Append a quad (two triangles) with a single face normal."""
        ni = self._ni(normal)
        ia, ib, ic, idx = (self._vi(p) for p in (a, b, c, d))
        faces = [[(ia, ni), (ib, ni), (ic, ni)], [(ia, ni), (ic, ni), (idx, ni)]]
        self.groups.append((mat, faces))

    def tri(self, mat, a, b, c, normal=None):
        if normal is None:
            u = tuple(b[i] - a[i] for i in range(3))
            w = tuple(c[i] - a[i] for i in range(3))
            normal = (
                u[1] * w[2] - u[2] * w[1],
                u[2] * w[0] - u[0] * w[2],
                u[0] * w[1] - u[1] * w[0],
            )
        ni = self._ni(normal)
        ia, ib, ic = (self._vi(p) for p in (a, b, c))
        self.groups.append((mat, [[(ia, ni), (ib, ni), (ic, ni)]]))

    def box(self, mat, x0, x1, y0, y1, z0, z1, faces="xXyYzZ"):
        """Axis-aligned box; `faces` selects which sides to emit (x=-X, X=+X,
        y=-Y bottom, Y=+Y top, z=-Z, Z=+Z)."""
        c = {
            "000": (x0, y0, z0), "100": (x1, y0, z0), "110": (x1, y0, z1), "010": (x0, y0, z1),
            "001": (x0, y1, z0), "101": (x1, y1, z0), "111": (x1, y1, z1), "011": (x0, y1, z1),
        }
        if "y" in faces:
            self.quad(mat, c["000"], c["100"], c["110"], c["010"], (0, -1, 0))
        if "Y" in faces:
            self.quad(mat, c["001"], c["011"], c["111"], c["101"], (0, 1, 0))
        if "z" in faces:
            self.quad(mat, c["000"], c["001"], c["101"], c["100"], (0, 0, -1))
        if "Z" in faces:
            self.quad(mat, c["010"], c["110"], c["111"], c["011"], (0, 0, 1))
        if "x" in faces:
            self.quad(mat, c["000"], c["010"], c["011"], c["001"], (-1, 0, 0))
        if "X" in faces:
            self.quad(mat, c["100"], c["101"], c["111"], c["110"], (1, 0, 0))

    def pyramid(self, mat, x0, x1, z0, z1, y0, apex):
        """Four triangular slopes from a rectangle up to an apex point."""
        a, b, cc, d = (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)
        self.tri(mat, a, b, apex)
        self.tri(mat, b, cc, apex)
        self.tri(mat, cc, d, apex)
        self.tri(mat, d, a, apex)

    def gable_roof(self, mat, x0, x1, z0, z1, y0, ridge_y):
        """A roof with the ridge running along X (peaks over the Z mid-line)."""
        zm = (z0 + z1) / 2
        r0, r1 = (x0, ridge_y, zm), (x1, ridge_y, zm)
        self.quad(mat, (x0, y0, z1), (x1, y0, z1), r1, r0, (0, 0.7, 0.7))
        self.quad(mat, (x1, y0, z0), (x0, y0, z0), r0, r1, (0, 0.7, -0.7))
        self.tri(mat, (x0, y0, z0), (x0, y0, z1), r0, (-1, 0, 0))
        self.tri(mat, (x1, y0, z1), (x1, y0, z0), r1, (1, 0, 0))

    def ngon_prism(self, mat, cx, cz, radius, y0, y1, n=8, *, top=True, bottom=True):
        """A vertical n-gon prism (a low cylinder), centred at (cx, cz)."""
        ring = [
            (cx + radius * math.cos(2 * math.pi * k / n),
             cz + radius * math.sin(2 * math.pi * k / n))
            for k in range(n)
        ]
        for k in range(n):
            x0, z0 = ring[k]
            x1, z1 = ring[(k + 1) % n]
            nrm = (math.cos(2 * math.pi * (k + 0.5) / n), 0.0,
                   math.sin(2 * math.pi * (k + 0.5) / n))
            self.quad(mat, (x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0), nrm)
        if bottom:
            for k in range(1, n - 1):
                self.tri(mat, (ring[0][0], y0, ring[0][1]), (ring[k + 1][0], y0, ring[k + 1][1]),
                         (ring[k][0], y0, ring[k][1]), (0, -1, 0))
        if top:
            for k in range(1, n - 1):
                self.tri(mat, (ring[0][0], y1, ring[0][1]), (ring[k][0], y1, ring[k][1]),
                         (ring[k + 1][0], y1, ring[k + 1][1]), (0, 1, 0))

    def cone(self, mat, cx, cz, radius, y0, apex_y, n=8):
        """An n-gon cone (e.g. a canopy), apex on the central axis."""
        apex = (cx, apex_y, cz)
        ring = [
            (cx + radius * math.cos(2 * math.pi * k / n),
             cz + radius * math.sin(2 * math.pi * k / n))
            for k in range(n)
        ]
        for k in range(n):
            x0, z0 = ring[k]
            x1, z1 = ring[(k + 1) % n]
            self.tri(mat, (x0, y0, z0), (x1, y0, z1), apex)

    def annulus(self, mat, r_out, r_in, z0, z1, n=24):
        """A flat ring (the wheel rim) in the X-Y plane, thin along Z."""
        def pt(r, k, z):
            a = 2 * math.pi * k / n
            return (r * math.cos(a), r * math.sin(a), z)
        for k in range(n):
            ko, kn = k, (k + 1) % n
            # front (+Z) and back (-Z) ring faces
            self.quad(mat, pt(r_in, ko, z1), pt(r_out, ko, z1),
                      pt(r_out, kn, z1), pt(r_in, kn, z1), (0, 0, 1))
            self.quad(mat, pt(r_out, ko, z0), pt(r_in, ko, z0),
                      pt(r_in, kn, z0), pt(r_out, kn, z0), (0, 0, -1))
            # outer + inner rims
            ao = 2 * math.pi * (ko + 0.5) / n
            self.quad(mat, pt(r_out, ko, z0), pt(r_out, kn, z0),
                      pt(r_out, kn, z1), pt(r_out, ko, z1), (math.cos(ao), math.sin(ao), 0))
            self.quad(mat, pt(r_in, kn, z0), pt(r_in, ko, z0),
                      pt(r_in, ko, z1), pt(r_in, kn, z1), (-math.cos(ao), -math.sin(ao), 0))

    def flat_strut(self, mat, p0, p1, width, z0, z1):
        """A thin radial slab (a wheel spoke) between two X-Y points."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy) or 1.0
        px, py = -dy / length * width / 2, dx / length * width / 2
        a, b = (p0[0] + px, p0[1] + py), (p0[0] - px, p0[1] - py)
        c, d = (p1[0] - px, p1[1] - py), (p1[0] + px, p1[1] + py)
        for z, nz in ((z1, 1), (z0, -1)):
            self.quad(mat, (a[0], a[1], z), (d[0], d[1], z),
                      (c[0], c[1], z), (b[0], b[1], z), (0, 0, nz))
        for (s, e) in (((a, d)), ((d, c)), ((c, b)), ((b, a))):
            nx, ny = (e[1] - s[1]), -(e[0] - s[0])
            self.quad(mat, (s[0], s[1], z0), (e[0], e[1], z0),
                      (e[0], e[1], z1), (s[0], s[1], z1), (nx, ny, 0))

    def write(self, path: Path) -> None:
        lines = [f"# {self.header}",
                 "# OBJ space: +X forward, +Y up, +Z right; origin at footprint-base centre.",
                 "mtllib materials.mtl", ""]
        lines += [f"v {p[0]:g} {p[1]:g} {p[2]:g}" for p in self.v]
        lines.append("")
        lines += [f"vn {n[0]:g} {n[1]:g} {n[2]:g}" for n in self.vn]
        last_mat = None
        for mat, faces in self.groups:
            if mat != last_mat:
                lines += ["", f"usemtl {mat}"]
                last_mat = mat
            for f in faces:
                lines.append("f " + " ".join(f"{vi}//{ni}" for vi, ni in f))
        path.write_text("\n".join(lines) + "\n")
        print(f"wrote {path.relative_to(REPO)}  "
              f"({len(self.v)} verts, {sum(len(g[1]) for g in self.groups)} tris)")


# ── Shops / facilities ────────────────────────────────────────────────────────
def food_stall():
    o = ObjBuilder("Burger bar (food_stall): booth + serving counter + flat canopy.")
    o.box("Wood", -1.2, 1.2, 0.0, 1.6, -1.2, 1.2, faces="xXyzZ")
    o.box("Wood", 1.2, 1.55, 0.85, 1.05, -1.2, 1.2)
    o.box("Red", -1.0, 1.0, 1.15, 1.55, 1.21, 1.22, faces="Z")
    o.box("Remap1", -1.45, 1.7, 1.6, 1.85, -1.45, 1.45)
    o.write(STALL / "burger_bar.obj")


def drink_stall():
    o = ObjBuilder("Drinks stand (drink_stall): booth + counter + pitched canopy.")
    o.box("Wood", -1.2, 1.2, 0.0, 1.5, -1.2, 1.2, faces="xXyzZ")
    o.box("Wood", 1.2, 1.5, 0.8, 0.98, -1.2, 1.2)
    o.box("Metal", -0.5, 0.5, 1.5, 2.0, -0.1, 0.1)
    o.pyramid("Remap1", -1.5, 1.6, -1.5, 1.5, 1.7, (0.05, 2.5, 0.0))
    o.write(STALL / "drinks_stand.obj")


def shop():
    o = ObjBuilder("Souvenir shop (shop): kiosk with a glazed front + awning + goods.")
    o.box("Wood", -1.2, 1.2, 0.0, 1.8, -1.2, 1.2, faces="xyzZ")
    o.box("Glass", 1.18, 1.22, 0.9, 1.6, -1.0, 1.0, faces="xX")
    o.box("Wood", 1.18, 1.22, 0.0, 0.9, -1.2, 1.2, faces="X")
    o.box("Wood", 1.18, 1.22, 1.6, 1.8, -1.2, 1.2, faces="X")
    o.box("Remap1", -1.3, 1.7, 1.78, 1.95, -1.3, 1.3)
    o.write(STALL / "souvenir_shop.obj")


def information_kiosk():
    o = ObjBuilder("Information kiosk (information_kiosk): square booth + pointed roof + board.")
    o.box("Wood", -1.0, 1.0, 0.0, 1.7, -1.0, 1.0, faces="xXyzZ")
    o.box("White", 1.0, 1.04, 0.9, 1.5, -0.8, 0.8, faces="X")
    o.box("Remap1", -1.2, 1.2, 1.7, 1.78, -1.2, 1.2)
    o.pyramid("Remap1", -1.2, 1.2, -1.2, 1.2, 1.78, (0.0, 2.6, 0.0))
    o.write(STALL / "information_kiosk.obj")


def cash_machine():
    o = ObjBuilder("Cash machine (cash_machine): a free-standing ATM cabinet, screen on +X.")
    o.box("Remap1", -0.5, 0.5, 0.0, 2.0, -0.7, 0.7)
    o.box("Screen", 0.5, 0.52, 1.25, 1.75, -0.45, 0.45, faces="X")
    o.box("Metal", 0.5, 0.62, 0.95, 1.15, -0.35, 0.35, faces="XY")
    o.write(STALL / "atm.obj")


def first_aid():
    o = ObjBuilder("First aid room (first_aid facility): white building, red cross, gable roof.")
    o.box("White", -1.3, 1.3, 0.0, 2.0, -1.3, 1.3, faces="xXyzZ")
    o.box("Red", 1.30, 1.34, 1.0, 1.5, -0.25, 0.25, faces="X")
    o.box("Red", 1.30, 1.34, 1.13, 1.37, -0.5, 0.5, faces="X")
    o.gable_roof("RoofSlate", -1.45, 1.45, -1.45, 1.45, 2.0, 2.7)
    o.write(STALL / "first_aid.obj")
    d = ObjBuilder("First aid doorway (door: true), facing OBJ +X.")
    d.box("DoorWood", 1.28, 1.32, 0.0, 1.3, -0.45, 0.45, faces="X")
    d.write(STALL / "first_aid_door.obj")


# ── 3x3 building rides ────────────────────────────────────────────────────────
def crooked_house():
    o = ObjBuilder("Crooked house (crooked_house, 3x3 building): a wonky two-storey cottage.")
    sx, sz = 0.9, 0.6
    x0, x1, z0, z1 = -2.2, 2.2, -2.2, 2.2
    y0, y1 = 0.0, 4.0
    b = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]
    t = [(x0 + sx, y1, z0 + sz), (x1 + sx, y1, z0 + sz),
         (x1 + sx, y1, z1 + sz), (x0 + sx, y1, z1 + sz)]
    o.quad("Wood", b[0], b[1], b[2], b[3], (0, -1, 0))
    o.quad("Wood", b[0], t[0], t[1], b[1], (0, -0.2, -1))
    o.quad("Wood", b[1], t[1], t[2], b[2], (1, -0.2, 0))
    o.quad("Wood", b[2], t[2], t[3], b[3], (0, -0.2, 1))
    o.quad("Wood", b[3], t[3], t[0], b[0], (-1, -0.2, 0))
    o.pyramid("Remap1", x0 + sx, x1 + sx, z0 + sz, z1 + sz, y1, (sx + 0.6, 5.6, sz + 0.4))
    o.box("DoorWood", x1 + 0.4 * sx, x1 + 0.4 * sx + 0.05, 0.0, 1.6, -0.5, 0.5, faces="X")
    o.write(BUILD / "crooked_house.obj")


def haunted_house():
    o = ObjBuilder("Haunted house (haunted_house, 3x3 building): spooky mansion with a tower.")
    o.box("DarkWood", -2.2, 2.2, 0.0, 3.4, -2.2, 2.2, faces="xXyzZ")
    o.gable_roof("RoofSlate", -2.4, 2.4, -2.4, 2.4, 3.4, 4.8)
    o.box("DarkWood", 1.2, 2.2, 0.0, 4.6, -2.2, -1.2, faces="xXyzZ")
    o.pyramid("RoofSlate", 1.1, 2.3, -2.3, -1.1, 4.6, (1.7, 6.0, -1.7))
    o.box("DoorWood", 2.2, 2.24, 0.0, 1.8, -0.6, 0.6, faces="X")
    o.box("Remap1", 2.2, 2.24, 2.2, 2.9, -1.6, -0.8, faces="X")
    o.box("Remap1", 2.2, 2.24, 2.2, 2.9, 0.8, 1.6, faces="X")
    o.write(BUILD / "haunted_house.obj")


# ── Animated flat rides ───────────────────────────────────────────────────────
def carousel():
    o = ObjBuilder(
        "Merry-go-round (merry_go_round flat ride): a 4-fold-symmetric carousel.\n"
        "# Authored centred on the middle tile, spun about +Y by animation.frames."
    )
    o.ngon_prism("Remap2", 0, 0, 2.0, 0.0, 0.35, n=16, bottom=True, top=True)
    o.ngon_prism("Brass", 0, 0, 0.22, 0.35, 3.3, n=8)
    for k in range(8):
        a = 2 * math.pi * k / 8
        hx, hz = 1.45 * math.cos(a), 1.45 * math.sin(a)
        o.ngon_prism("Brass", hx, hz, 0.07, 0.35, 3.0, n=6)
        bx, bz = 0.42, 0.22
        if k % 2 == 0:
            o.box("Wood", hx - bx, hx + bx, 0.95, 1.5, hz - bz, hz + bz)
        else:
            o.box("Wood", hx - bz, hx + bz, 0.95, 1.5, hz - bx, hz + bx)
        o.box("Remap1", hx - 0.3, hx + 0.3, 1.5, 1.58, hz - 0.18, hz + 0.18, faces="Y")
    o.ngon_prism("Canvas", 0, 0, 2.25, 2.5, 2.7, n=16, bottom=False, top=False)
    o.cone("Remap1", 0, 0, 2.3, 2.6, 3.7, n=16)
    o.ngon_prism("Brass", 0, 0, 0.12, 3.3, 3.9, n=6)
    o.write(BUILD / "carousel.obj")


# Ferris wheel geometry, shared by the mesh builders and the spin emitter so the
# orbiting gondolas line up with the rim. The wheel disc is authored in the X-Y
# plane (axle along Z) centred at the origin; the spin lifts it to the axle.
FERRIS_FRAMES = 8
FERRIS_GONDOLAS = 8
FERRIS_RADIUS = 3.0
FERRIS_AXLE_Y = 3.6
# 8 frames span one gondola spacing (45 deg), so the 8-fold-symmetric wheel loops
# seamlessly: frame 8 == frame 0 with every gondola advanced one seat.
FERRIS_SPIN_STEP = (360.0 / FERRIS_GONDOLAS) / FERRIS_FRAMES


def ferris_wheel():
    o = ObjBuilder(
        "Ferris wheel (ferris_wheel flat ride): the rotating wheel only.\n"
        "# Disc in the X-Y plane, axle along Z, centred at the origin (the spin\n"
        "# lifts it to the axle). The A-frame legs are base-game graphics, so the\n"
        "# object provides only the wheel; gondola.obj orbits as a second mesh."
    )
    r = FERRIS_RADIUS
    o.box("Brass", -0.35, 0.35, -0.35, 0.35, -0.18, 0.18)  # hub
    for k in range(FERRIS_GONDOLAS):
        a = 2 * math.pi * k / FERRIS_GONDOLAS
        o.flat_strut(
            "Brass", (0.3 * math.cos(a), 0.3 * math.sin(a)),
            (r * math.cos(a), r * math.sin(a)), 0.12, -0.06, 0.06,
        )
    o.annulus("Remap1", r + 0.15, r - 0.15, -0.12, 0.12, n=32)
    o.write(BUILD / "ferris_wheel.obj")


def ferris_gondola():
    o = ObjBuilder(
        "Ferris wheel gondola: a cabin hanging from its rim point (top at the\n"
        "# origin so it hangs below wherever animation.frames places it)."
    )
    o.box("Brass", -0.04, 0.04, -0.15, 0.0, -0.04, 0.04)  # hanger bar
    o.box("Remap2", -0.32, 0.32, -0.78, -0.15, -0.26, 0.26)  # cabin
    o.box("RoofSlate", -0.34, 0.34, -0.15, -0.08, -0.28, 0.28)  # roof
    o.write(BUILD / "gondola.obj")


def _merry_go_round_frames() -> list[str]:
    lines = []
    for i in range(MERRY_GO_ROUND_FRAMES):
        yaw = round(360.0 * i / MERRY_GO_ROUND_FRAMES, 3)
        lines.append(
            f"    - [{{mesh_index: 0, position: [0, 0, 0], "
            f"orientation: [{yaw:g}, 0, 0]}}]"
        )
    return lines


def _ferris_wheel_frames() -> list[str]:
    lines = []
    for f in range(FERRIS_FRAMES):
        spin = f * FERRIS_SPIN_STEP
        # The wheel (mesh 0): spin about Z (axle), lifted to the axle height.
        parts = [
            f"{{mesh_index: 0, position: [0, {FERRIS_AXLE_Y:g}, 0], "
            f"orientation: [0, {round(spin, 3):g}, 0]}}"
        ]
        # Each gondola (mesh 1): orbits on the rim, staying upright.
        for g in range(FERRIS_GONDOLAS):
            ang = math.radians(g * 360.0 / FERRIS_GONDOLAS + spin)
            x = round(FERRIS_RADIUS * math.cos(ang), 3)
            y = round(FERRIS_AXLE_Y + FERRIS_RADIUS * math.sin(ang), 3)
            parts.append(
                f"{{mesh_index: 1, position: [{x:g}, {y:g}, 0], orientation: [0, 0, 0]}}"
            )
        # Continuation lines align under the first element (7 leading spaces) so
        # yamllint is happy with the multi-line flow sequence.
        lines.append("    - [" + ",\n       ".join(parts) + "]")
    return lines


def print_spin(ride: str) -> None:
    """Re-emit a flat ride's `animation.frames` block for its example config."""
    emit = {"merry_go_round": _merry_go_round_frames, "ferris_wheel": _ferris_wheel_frames}
    print("animation:")
    print("  frames:")
    print("\n".join(emit[ride]()))


BUILDERS = (
    food_stall, drink_stall, shop, information_kiosk, cash_machine, first_aid,
    crooked_house, haunted_house, carousel, ferris_wheel, ferris_gondola,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-spin", choices=("merry_go_round", "ferris_wheel"),
        help="print the named flat ride's animation.frames block and exit",
    )
    args = parser.parse_args()
    if args.print_spin:
        print_spin(args.print_spin)
        return
    for builder in BUILDERS:
        builder()


if __name__ == "__main__":
    main()
