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


# The carousel's visible riders: one seat's rider-pair, rendered by the engine at
# 68 of 128 orbit positions (the front-visible arc). Authored at a horse (radius
# 1.45 along +X, seat height) so the rider ring rotates it about +Y to each orbit
# angle, exactly like the platform spin. The two riders are Remap1 / Remap2 so the
# engine tints each by its peep's t-shirt colour.
CAROUSEL_RIDER_RADIUS = 1.45
CAROUSEL_RIDER_FRAMES = 68


def carousel_rider():
    o = ObjBuilder(
        "Merry-go-round riders (placeholder): a seated pair on a horse.\n"
        "# Remap1 / Remap2 are the two riders' shirts (the engine tints each by a\n"
        "# peep's t-shirt colour). Authored at horse 0 (radius 1.45 along +X); the\n"
        "# rider ring rotates it about +Y to each of 68 orbit poses."
    )
    cx = CAROUSEL_RIDER_RADIUS
    for mat, z0, z1 in (("Remap1", -0.30, -0.02), ("Remap2", 0.02, 0.30)):
        o.box(mat, cx - 0.24, cx + 0.24, 1.55, 2.0, z0, z1)  # torso
        o.box("Skin", cx - 0.13, cx + 0.13, 2.0, 2.26, (z0 + z1) / 2 - 0.13,
              (z0 + z1) / 2 + 0.13)  # head
    o.write(BUILD / "carousel_rider.obj")


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


# The ferris wheel's visible riders: one gondola's rider-pair. Authored hanging
# from the origin (the rim attachment, like gondola.obj) so the rider ring orbits
# it upright -- a pure translation around the axle, never a rotation -- to each of
# 128 positions, per view direction. Remap1 / Remap2 are the two shirts.
FERRIS_RIDER_FRAMES = 128


def ferris_rider():
    o = ObjBuilder(
        "Ferris wheel riders (placeholder): a seated pair inside a gondola.\n"
        "# Remap1 / Remap2 are the two riders' shirts. Authored hanging from the\n"
        "# origin (the rim attachment) so the rider ring orbits it upright to each\n"
        "# of 128 positions, like the gondola it rides in."
    )
    for mat, x0, x1 in (("Remap1", -0.26, -0.02), ("Remap2", 0.02, 0.26)):
        o.box(mat, x0, x1, -0.58, -0.28, -0.2, 0.2)  # torso
        o.box("Skin", (x0 + x1) / 2 - 0.1, (x0 + x1) / 2 + 0.1, -0.28, -0.1,
              -0.1, 0.1)  # head
    o.write(BUILD / "ferris_rider.obj")


# The twist's visible riders: one tub's rider-pair, rendered at 216 rotation
# phases of the full turn (Twist.cpp `base + 24 + (frameNum + seat*12) % 216`),
# single view. Authored in a rim tub (radius 1.5 along +X); the rider ring rotates
# it about +Y like the platform. Remap1 / Remap2 are the two shirts.
TWIST_RIDER_RADIUS = 1.5
TWIST_RIDER_FRAMES = 216


def twist_rider():
    o = ObjBuilder(
        "Twist riders (placeholder): a seated pair in a rim tub.\n"
        "# Remap1 / Remap2 are the two riders' shirts. Authored at tub 0 (radius\n"
        "# 1.5 along +X); the rider ring rotates it about +Y to each of 216 phases."
    )
    cx = TWIST_RIDER_RADIUS
    for mat, z0, z1 in (("Remap1", -0.26, -0.02), ("Remap2", 0.02, 0.26)):
        o.box(mat, cx - 0.2, cx + 0.2, 1.0, 1.45, z0, z1)  # torso
        o.box("Skin", cx - 0.1, cx + 0.1, 1.45, 1.66, (z0 + z1) / 2 - 0.1,
              (z0 + z1) / 2 + 0.1)  # head
    o.write(BUILD / "twist_rider.obj")


# The enterprise's visible riders: a single rider in a pod. The pods are enclosed,
# so the engine shows riders only near the bottom -- 3 animation sub-frames x 16
# folded angular positions (Enterprise.cpp `base + 196 + ...`), a single view.
# Authored in pod 0 (radius 3.4 along +X, in the wheel's X-Y plane); the rider ring
# rotates it about the axle (Z) with the wheel. Remap1 is the rider's shirt.
ENTERPRISE_RIDER_FRAMES = 48


def enterprise_rider():
    o = ObjBuilder(
        "Enterprise rider (placeholder): a single rider in a pod.\n"
        "# Remap1 is the rider's shirt. Authored in pod 0 (radius 3.4 along +X in\n"
        "# the wheel's X-Y plane); the rider ring rotates it about the axle (Z) with\n"
        "# the wheel. The pods are enclosed, so the engine shows riders only at the\n"
        "# bottom: 48 poses (3 sub-frames x 16 folded angles), single view."
    )
    cx = ENTERPRISE_RADIUS
    o.box("Remap1", cx - 0.2, cx + 0.2, -0.2, 0.22, -0.16, 0.16)  # torso
    o.box("Skin", cx - 0.1, cx + 0.1, 0.22, 0.42, -0.1, 0.1)  # head
    o.write(BUILD / "enterprise_rider.obj")


# The space rings' visible rider: one rider on the ring's seat, tumbling with the
# ring (SpaceRings.cpp `base + 352 + direction + frame*4`) -- the same 4 directions
# x 88 poses as the structure. Authored on the seat at the ring's bottom; Remap1 is
# the shirt, Remap2 the trousers (the engine tints each separately).
SPACE_RINGS_RIDER_FRAMES = 88


def space_rings_rider():
    o = ObjBuilder(
        "Space rings rider (placeholder): one rider on the ring's seat.\n"
        "# Remap1 is the shirt, Remap2 the trousers. Authored on the seat at the\n"
        "# ring's bottom; the rider tumbles with the ring (4 directions x 88 poses)."
    )
    cy = -SPACE_RINGS_RADIUS + 0.2  # seat top, at the ring's bottom rim
    o.box("Remap2", -0.2, 0.2, cy, cy + 0.26, -0.2, 0.2)  # legs / trousers
    o.box("Remap1", -0.2, 0.2, cy + 0.26, cy + 0.56, -0.2, 0.2)  # torso / shirt
    o.box("Skin", -0.1, 0.1, cy + 0.56, cy + 0.76, -0.1, 0.1)  # head
    o.write(BUILD / "space_rings_rider.obj")


# The swinging ship's visible riders: 8 bench rows of rider-pairs, each filling a
# sub-slot after its ship sprite (SwingingShip.cpp `base + ship + 1 + row*2 +
# ((dir>>1)^col)`). One rider-pair authored at the OBJ origin; the rider rows place
# it at 8 bench positions (4 fore-aft x 2 port/starboard) and swing it with the
# ship. Remap1 / Remap2 are the two shirts.
SWINGING_SHIP_BENCH_ROWS = 8
SWINGING_SHIP_BENCH_Y = -2.0  # OBJ +Y of the bench seats, just above the deck


def swinging_ship_rider():
    o = ObjBuilder(
        "Swinging ship riders (placeholder): one bench's rider-pair.\n"
        "# Remap1 / Remap2 are the two shirts. Authored at the OBJ origin; the 8\n"
        "# rider rows place it at the benches (4 fore-aft x 2 port/starboard) and\n"
        "# swing it with the ship about +Z."
    )
    for mat, x0, x1 in (("Remap1", -0.32, -0.04), ("Remap2", 0.04, 0.32)):
        o.box(mat, x0, x1, 0.0, 0.42, -0.18, 0.18)  # torso
        o.box("Skin", (x0 + x1) / 2 - 0.09, (x0 + x1) / 2 + 0.09, 0.42, 0.62,
              -0.09, 0.09)  # head
    o.write(BUILD / "swinging_ship_rider.obj")


TWIST_FRAMES = 24


def twist():
    o = ObjBuilder(
        "Twist (twist flat ride): a 4-fold-symmetric spinning platform with tubs.\n"
        "# Authored centred on the middle tile, spun about +Y by animation.frames\n"
        "# (one symmetric ring the engine reuses for every view, like the carousel)."
    )
    # Base platform disc (trim colour) + central pole and canopy.
    o.ngon_prism("Remap2", 0, 0, 2.2, 0.0, 0.3, n=16, bottom=True, top=True)
    o.ngon_prism("Brass", 0, 0, 0.24, 0.3, 2.6, n=8)
    o.cone("Remap1", 0, 0, 1.0, 2.6, 3.5, n=12)
    # Four tubs at the rim, 4-fold symmetric so the single rendered view holds for
    # every camera direction.
    for k in range(4):
        a = 2 * math.pi * k / 4
        cx, cz = 1.5 * math.cos(a), 1.5 * math.sin(a)
        o.ngon_prism("Remap1", cx, cz, 0.62, 0.3, 1.0, n=8, bottom=True, top=False)
        o.ngon_prism("Wood", cx, cz, 0.66, 0.95, 1.08, n=8, bottom=False, top=False)
    o.write(BUILD / "twist.obj")


# Enterprise geometry: a vertical wheel (disc in the X-Y plane, axle along Z,
# centred at the origin) whose pods are rigidly attached, so the whole wheel is
# one mesh spun about its axle (riders invert, unlike the ferris wheel's upright
# gondolas). The truss supports are base-game graphics, so the object provides
# only the wheel; the spin lifts it to the hub height.
ENTERPRISE_FRAMES = 49
ENTERPRISE_PODS = 10
ENTERPRISE_RADIUS = 3.4
ENTERPRISE_HUB_Y = 4.2
# 49 frames span one full turn (each 360/49 deg), so frame 49 == frame 0.
ENTERPRISE_SPIN_STEP = 360.0 / ENTERPRISE_FRAMES


def enterprise():
    o = ObjBuilder(
        "Enterprise (enterprise flat ride): the rotating wheel with rigidly-\n"
        "# attached pods. Disc in the X-Y plane, axle along Z, centred at the origin\n"
        "# (the spin lifts it to the hub). The truss supports are base-game\n"
        "# graphics, so the object provides only the wheel; the pods rotate WITH the\n"
        "# wheel (riders invert), unlike the ferris wheel's upright gondolas."
    )
    r = ENTERPRISE_RADIUS
    o.box("Brass", -0.4, 0.4, -0.4, 0.4, -0.2, 0.2)  # hub
    for k in range(ENTERPRISE_PODS):
        a = 2 * math.pi * k / ENTERPRISE_PODS
        cx, cy = r * math.cos(a), r * math.sin(a)
        # Spoke from the hub out to the rim.
        o.flat_strut("Metal", (0.32 * math.cos(a), 0.32 * math.sin(a)),
                     (cx, cy), 0.1, -0.04, 0.04)
        # Enclosed pod at the rim (cabin + canopy) straddling the rim point.
        o.box("Remap2", cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42, -0.3, 0.3)
        o.box("Brass", cx - 0.46, cx + 0.46, cy - 0.46, cy + 0.46, 0.3, 0.36, faces="Z")
    o.annulus("Remap1", r + 0.2, r - 0.2, -0.13, 0.13, n=32)  # outer rim
    o.write(BUILD / "enterprise.obj")


# Motion simulator: the tilting pod only (the boarding stairs are base-game
# graphics). Authored centred on the OBJ origin so a pose tilts it about its own
# centre, then lifts it onto its cradle. 35 poses: frames 0-3 are the restraint
# load stages (held level), frames 4-34 the tilt motion in pitch/roll groups
# that mirror the engine's sprite layout (each group eases out and back to level
# so the engine's jumps between groups stay smooth).
MOTION_SIMULATOR_FRAMES = 35
MOTION_SIMULATOR_LIFT = 1.7
MOTION_SIMULATOR_PITCH = 18.0  # degrees about +Z (nose up/down)
MOTION_SIMULATOR_ROLL = 15.0  # degrees about +X (bank left/right)


def motion_simulator():
    o = ObjBuilder(
        "Motion simulator (motion_simulator flat ride): the tilting pod only.\n"
        "# Authored centred on the OBJ origin so animation.frames can tilt it about\n"
        "# its own centre (pitch about +Z, roll about +X) and lift it onto its\n"
        "# cradle. The boarding stairs are base-game graphics, so the object\n"
        "# provides only the pod; 4 view directions x 35 tilt poses."
    )
    o.box("Remap1", -1.3, 1.3, -0.55, 0.55, -0.85, 0.85, faces="xXyYz")  # cabin
    o.box("Metal", 1.3, 1.34, -0.4, 0.4, -0.7, 0.7, faces="X")  # screen-end face
    o.box("Wood", -1.32, 1.32, 0.55, 0.62, -0.87, 0.87, faces="Y")  # roof cap
    o.box("Brass", -0.22, 0.22, -0.95, -0.55, -0.3, 0.3)  # cradle stub below
    o.write(BUILD / "motion_simulator.obj")


def _motion_simulator_pose(pitch: float, roll: float) -> str:
    return (
        f"{{mesh_index: 0, position: [0, {MOTION_SIMULATOR_LIFT:g}, 0], "
        f"orientation: [0, {round(pitch, 3):g}, {round(roll, 3):g}]}}"
    )


def _motion_simulator_frames() -> list[str]:
    p, r = MOTION_SIMULATOR_PITCH, MOTION_SIMULATOR_ROLL
    poses: list[tuple[float, float]] = [(0.0, 0.0)] * 4  # 0-3: restraint load stages
    # Each motion group eases from level out to its excursion and back (sin over
    # six steps), matching the engine's six-wide pitch / roll / combo sprite groups.
    bumps = [math.sin(math.pi * k / 5) for k in range(6)]
    poses += [(p * b, 0.0) for b in bumps]  # 4-9: pitch up
    poses += [(0.0, 0.0)]  # 10: level
    poses += [(-p * b, 0.0) for b in bumps]  # 11-16: pitch down
    poses += [(0.0, r * b) for b in bumps]  # 17-22: roll
    poses += [(0.7 * p * b, 0.7 * r * b) for b in bumps]  # 23-28: pitch + roll
    poses += [(-0.7 * p * b, 0.7 * r * b) for b in bumps]  # 29-34: pitch - roll
    assert len(poses) == MOTION_SIMULATOR_FRAMES
    return [f"    - [{_motion_simulator_pose(pitch, roll)}]" for pitch, roll in poses]


# Swinging ship: the boat + its swing beams only (the A-frame supports are
# base-game graphics). Authored hanging from the OBJ origin (the swing axis) so a
# pose swings it about +Z and lifts the pivot onto the A-frame. 19 swing-block
# poses: block 0 upright, blocks 1-9 lean one way, 10-18 the other (the engine's
# image order); the add-on samples a keyframed swing into this order.
SWINGING_SHIP_FRAMES = 19
SWINGING_SHIP_PIVOT = 3.6  # OBJ +Y height lifting the swing axis onto the A-frame
SWINGING_SHIP_AMPLITUDE = 52.0  # max swing angle, degrees about +Z


def swinging_ship():
    o = ObjBuilder(
        "Swinging ship (swinging_ship flat ride): the boat + swing beams only.\n"
        "# Authored hanging from the OBJ origin (the swing axis) so animation.frames\n"
        "# can swing it about +Z and lift the pivot onto the base-game A-frame. The\n"
        "# supports are base-game graphics, so the object provides only the ship;\n"
        "# 2 camera planes x 19 swing poses (+8 blank rider slots each)."
    )
    # Swing beams hanging from the pivot (origin) down to the deck.
    o.box("Brass", -0.13, 0.13, -2.3, 0.05, -0.95, -0.75)
    o.box("Brass", -0.13, 0.13, -2.3, 0.05, 0.75, 0.95)
    # Hull along +X: a deck slab over a tapered hull, with raised bow/stern ends.
    o.box("Wood", -2.4, 2.4, -2.55, -2.25, -0.8, 0.8)  # deck
    o.box("Remap1", -2.1, 2.1, -3.3, -2.55, -0.65, 0.65)  # hull body
    o.box("Remap2", -2.5, -2.1, -3.1, -1.7, -0.55, 0.55)  # stern block
    o.box("Remap2", 2.1, 2.5, -3.1, -1.7, -0.55, 0.55)  # bow block
    o.write(BUILD / "swinging_ship.obj")


def _swinging_ship_pose(angle: float) -> str:
    return (
        f"{{mesh_index: 0, position: [0, {SWINGING_SHIP_PIVOT:g}, 0], "
        f"orientation: [0, {round(angle, 3):g}, 0]}}"
    )


def _swinging_ship_frames() -> list[str]:
    amp = SWINGING_SHIP_AMPLITUDE
    angles = [0.0]  # block 0: upright
    angles += [amp * r / 9 for r in range(1, 10)]  # blocks 1-9: lean one way
    angles += [-amp * r / 9 for r in range(1, 10)]  # blocks 10-18: lean the other
    assert len(angles) == SWINGING_SHIP_FRAMES
    return [f"    - [{_swinging_ship_pose(a)}]" for a in angles]


# Space rings: one tumbling ring (the engine spawns four). A ring disc in the
# X-Y plane, axle along Z, centred at the origin, with a seat on the rim that
# tumbles with it; the spin lifts it clear of the ground. A full 88-pose turn.
SPACE_RINGS_FRAMES = 88
SPACE_RINGS_RADIUS = 1.05
SPACE_RINGS_LIFT = 1.25
SPACE_RINGS_SPIN_STEP = 360.0 / SPACE_RINGS_FRAMES


def space_rings():
    o = ObjBuilder(
        "Space rings (space_rings flat ride): one tumbling ring (the engine spawns\n"
        "# four). Disc in the X-Y plane, axle along Z, centred at the origin so\n"
        "# animation.frames spins it and lifts it clear of the ground; a seat rides\n"
        "# the rim and tumbles with it. One ring x 4 directions x 88 spin poses."
    )
    r = SPACE_RINGS_RADIUS
    o.box("Brass", -0.18, 0.18, -0.18, 0.18, -0.12, 0.12)  # hub
    for k in range(4):
        a = 2 * math.pi * k / 4
        o.flat_strut(
            "Brass", (0.15 * math.cos(a), 0.15 * math.sin(a)),
            (r * math.cos(a), r * math.sin(a)), 0.08, -0.05, 0.05,
        )
    o.annulus("Remap1", r + 0.12, r - 0.12, -0.1, 0.1, n=24)  # ring rim
    o.box("Remap2", -0.28, 0.28, -r - 0.05, -r + 0.45, -0.28, 0.28)  # seat on the rim
    o.write(BUILD / "space_rings.obj")


def _space_rings_frames() -> list[str]:
    lines = []
    for f in range(SPACE_RINGS_FRAMES):
        spin = round(f * SPACE_RINGS_SPIN_STEP, 3)
        lines.append(
            f"    - [{{mesh_index: 0, position: [0, {SPACE_RINGS_LIFT:g}, 0], "
            f"orientation: [0, {spin:g}, 0]}}]"
        )
    return lines


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


def _merry_go_round_rider_frames() -> list[str]:
    # The carousel's rider ring is one seat's pair at ring positions 13..80 of 128
    # (MerryGoRound.cpp `base + 32 + ((seatOffset + rotation) % 128 - 13)`, valid
    # 0..67): rotate the rest pose (mesh 1) about +Y to each of those 68 angles.
    lines = []
    for s in range(CAROUSEL_RIDER_FRAMES):
        yaw = round((s + 13) * 360.0 / 128.0, 3)
        lines.append(
            f"    - [{{mesh_index: 1, position: [0, 0, 0], "
            f"orientation: [{yaw:g}, 0, 0]}}]"
        )
    return lines


def _ferris_wheel_rider_frames() -> list[str]:
    # The ferris wheel's rider ring is one gondola's pair orbiting the axle upright
    # at 128 positions (FerrisWheel.cpp `base + 32 + direction*128 + frame`):
    # translate the rest pose (mesh 2) around the rim, orientation fixed (upright).
    lines = []
    for s in range(FERRIS_RIDER_FRAMES):
        ang = math.radians(s * 360.0 / FERRIS_RIDER_FRAMES)
        x = round(FERRIS_RADIUS * math.cos(ang), 3)
        y = round(FERRIS_AXLE_Y + FERRIS_RADIUS * math.sin(ang), 3)
        lines.append(
            f"    - [{{mesh_index: 2, position: [{x:g}, {y:g}, 0], "
            f"orientation: [0, 0, 0]}}]"
        )
    return lines


def _twist_rider_frames() -> list[str]:
    # One tub's pair at 216 rotation phases of the full turn, about +Y (mesh 1).
    lines = []
    for s in range(TWIST_RIDER_FRAMES):
        yaw = round(s * 360.0 / TWIST_RIDER_FRAMES, 3)
        lines.append(
            f"    - [{{mesh_index: 1, position: [0, 0, 0], "
            f"orientation: [{yaw:g}, 0, 0]}}]"
        )
    return lines


def _enterprise_rider_frames() -> list[str]:
    # 48 poses = 3 animation sub-frames x 16 folded angular positions, ordered
    # `index = animFrame*16 + posIndex` (Enterprise.cpp). posIndex steps the pod a
    # coarse 22.5 deg; animFrame subdivides it by 7.5 deg. Rotate the pod rider
    # (mesh 1) about the axle (Z), lifted to the hub.
    lines = []
    for s in range(ENTERPRISE_RIDER_FRAMES):
        pos_index, anim_frame = s % 16, s // 16
        angle = round((pos_index * 3 + anim_frame) * 7.5, 3)
        lines.append(
            f"    - [{{mesh_index: 1, position: [0, {ENTERPRISE_HUB_Y:g}, 0], "
            f"orientation: [0, {angle:g}, 0]}}]"
        )
    return lines


def _space_rings_rider_frames() -> list[str]:
    # The rider tumbles with the ring: the same 88-pose spin about the axle (Z),
    # lifted clear of the ground (mesh 1), rendered at 4 directions by the engine.
    lines = []
    for f in range(SPACE_RINGS_RIDER_FRAMES):
        spin = round(f * 360.0 / SPACE_RINGS_RIDER_FRAMES, 3)
        lines.append(
            f"    - [{{mesh_index: 1, position: [0, {SPACE_RINGS_LIFT:g}, 0], "
            f"orientation: [0, {spin:g}, 0]}}]"
        )
    return lines


def _swinging_ship_swing_angles() -> list[float]:
    """The 19 swing-block angles, matching the structure's `animation.frames`."""
    amp = SWINGING_SHIP_AMPLITUDE
    return [0.0] + [amp * r / 9 for r in range(1, 10)] + [-amp * r / 9 for r in range(1, 10)]


def _swinging_ship_rider_rows() -> list[str]:
    # 8 bench rows (sub-slot k -> row k//2 fore-aft, col k%2 port/starboard), each a
    # rider-pair (mesh 1) authored at the origin and swung with the ship: the bench
    # offset is rotated about the pivot (+Z) by the swing angle, like the hull.
    lines = ["rider_rows:"]
    angles = _swinging_ship_swing_angles()
    for k in range(SWINGING_SHIP_BENCH_ROWS):
        row, col = k // 2, k % 2
        bx = 1.5 - row * 1.0
        bz = -0.5 + col * 1.0
        by = SWINGING_SHIP_BENCH_Y
        lines.append("  - frames:")
        for a_deg in angles:
            a = math.radians(a_deg)
            px = round(bx * math.cos(a) - by * math.sin(a), 3)
            py = round(SWINGING_SHIP_PIVOT + bx * math.sin(a) + by * math.cos(a), 3)
            lines.append(
                f"      - [{{mesh_index: 1, position: [{px:g}, {py:g}, {bz:g}], "
                f"orientation: [0, {round(a_deg, 3):g}, 0]}}]"
            )
    return lines


def _twist_frames() -> list[str]:
    lines = []
    for i in range(TWIST_FRAMES):
        yaw = round(360.0 * i / TWIST_FRAMES, 3)
        lines.append(
            f"    - [{{mesh_index: 0, position: [0, 0, 0], "
            f"orientation: [{yaw:g}, 0, 0]}}]"
        )
    return lines


def _enterprise_frames() -> list[str]:
    lines = []
    for f in range(ENTERPRISE_FRAMES):
        # The wheel (mesh 0): spin about Z (the axle), lifted to the hub height.
        spin = round(f * ENTERPRISE_SPIN_STEP, 3)
        lines.append(
            f"    - [{{mesh_index: 0, position: [0, {ENTERPRISE_HUB_Y:g}, 0], "
            f"orientation: [0, {spin:g}, 0]}}]"
        )
    return lines


def print_spin(ride: str) -> None:
    """Re-emit a flat ride's `animation.frames` block for its example config."""
    emit = {
        "merry_go_round": _merry_go_round_frames,
        "ferris_wheel": _ferris_wheel_frames,
        "twist": _twist_frames,
        "enterprise": _enterprise_frames,
        "motion_simulator": _motion_simulator_frames,
        "swinging_ship": _swinging_ship_frames,
        "space_rings": _space_rings_frames,
    }
    print("animation:")
    print("  frames:")
    print("\n".join(emit[ride]()))


# Rides whose riders form a trailing ring (`rider_animation.frames`).
RIDER_EMITTERS = {
    "merry_go_round": _merry_go_round_rider_frames,
    "ferris_wheel": _ferris_wheel_rider_frames,
    "twist": _twist_rider_frames,
    "enterprise": _enterprise_rider_frames,
    "space_rings": _space_rings_rider_frames,
}

# Rides whose riders are interleaved bench rows (`rider_rows`), emitting the whole
# block (the row layout is not a single frames list).
RIDER_ROW_EMITTERS = {
    "swinging_ship": _swinging_ship_rider_rows,
}


def print_riders(ride: str) -> None:
    """Re-emit a flat ride's rider block for its example config."""
    if ride in RIDER_ROW_EMITTERS:
        print("\n".join(RIDER_ROW_EMITTERS[ride]()))
        return
    print("rider_animation:")
    print("  frames:")
    print("\n".join(RIDER_EMITTERS[ride]()))


BUILDERS = (
    food_stall, drink_stall, shop, information_kiosk, cash_machine, first_aid,
    crooked_house, haunted_house, carousel, carousel_rider, ferris_wheel,
    ferris_gondola, ferris_rider, twist, twist_rider, enterprise, enterprise_rider,
    motion_simulator, swinging_ship, swinging_ship_rider, space_rings,
    space_rings_rider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-spin",
        choices=(
            "merry_go_round", "ferris_wheel", "twist", "enterprise", "motion_simulator",
            "swinging_ship", "space_rings",
        ),
        help="print the named flat ride's animation.frames block and exit",
    )
    parser.add_argument(
        "--print-riders",
        choices=tuple(RIDER_EMITTERS) + tuple(RIDER_ROW_EMITTERS),
        help="print the named flat ride's rider block (rider_animation / rider_rows) and exit",
    )
    args = parser.parse_args()
    if args.print_spin:
        print_spin(args.print_spin)
        return
    if args.print_riders:
        print_riders(args.print_riders)
        return
    for builder in BUILDERS:
        builder()


if __name__ == "__main__":
    main()
