# OpenRCT2 Ride Generator

A modern Blender add-on to author and export OpenRCT2 **stall, facility, 3x3
building, and animated flat ride objects** (food/drink stalls, shops, balloon
stalls, information kiosks, cash machines, toilets, first aid rooms, crooked
houses, haunted houses, circuses, merry-go-rounds, ferris wheels, twists, and
enterprises) from 3D
meshes. Geometry is ray-traced into the isometric sprite sheets OpenRCT2 expects
and packaged as a ready-to-install `.parkobj`.

Rendering is handled by the external [`openrct2-x7-renderer`](https://pypi.org/project/openrct2-x7-renderer/)
package (an Embree-backed ray tracer shipping prebuilt, vendored wheels).

Animated flat rides are driven by **Blender's animation timeline**: keyframe the
spin and the add-on samples it into the ride's rotation frames. The merry-go-round
and twist (one symmetric spin ring) and the ferris wheel and enterprise (four
directions of a wheel) ship today; more flat rides may follow.

## Requirements

- Windows x64, macOS arm64, Linux x64
- Blender 4.2 or newer

## Setup

1. Download the latest version of the Blender add-on [here](https://github.com/alex-parisi/OpenRCT2-RideGenerator/releases/latest)
2. Install the add-on into Blender

## CLI Usage

```
openrct2-ride-generator [--test|--skip-render] <input.json|.yaml>
```

- `--test`: render each view sprite to `test/` for fast iteration (no
  `.parkobj` produced).
- `--skip-render`: emit `object.json` / packaging without re-rendering sprites.

The config format is JSON or YAML (chosen by file extension). Relative
`meshes` / `preview` paths resolve against the config file's directory. The
`ride_type` field selects the stall type:

| `ride_type`         | Kind     | View sprites |
|---------------------|----------|--------------|
| `food_stall`        | shop     | 4            |
| `drink_stall`       | shop     | 4            |
| `shop`              | shop     | 4            |
| `balloon_stall`     | shop     | 4            |
| `information_kiosk` | shop     | 4            |
| `cash_machine`      | shop     | 4            |
| `toilets`           | facility | 6            |
| `first_aid`         | facility | 6            |
| `crooked_house`     | building  | 4            |
| `haunted_house`     | building  | 4 (+72)      |
| `circus`            | building  | 4            |
| `3d_cinema`         | building  | 4            |
| `merry_go_round`    | flat ride | 32 (+68)     |
| `ferris_wheel`      | flat ride | 32 (+512)    |
| `twist`             | flat ride | 24 (+216)    |
| `enterprise`        | flat ride | 196 (+48)    |
| `motion_simulator`  | flat ride | 140          |
| `swinging_ship`     | flat ride | 342          |
| `space_rings`       | flat ride | 352 (+352)   |

Building rides are the 3x3 flat rides whose whole structure is one sprite per
view direction. The model is authored **centred on the middle tile** (the 3x3
footprint allows up to 3 tiles across) and the `seats` property sets the
ride's capacity (defaults per type: 5 / 15 / 30 / 20). The 3D cinema paints
like the others but is filed under the **thrill** category rather than gentle.
The haunted house's 72 ghost-animation overlay slots are emitted blank, so the
ride operates normally but shows no popping ghost.

Animated flat rides are rides whose structure is a **vehicle sprite the engine
spins** by cycling a ring of rotation frames. The structure is authored once and
**animated** — in Blender, keyframe the spin and the add-on samples it into the
ring; in a CLI config, list one pose per frame under `animation.frames`. The
trailing rider slots are emitted blank (like the haunted house's ghosts), and
`seats` sets capacity. Four layouts ship today:

- **`merry_go_round`** — a 3x3 carousel, centred on the middle tile. The engine
  folds the camera rotation out (`base + frame`), so the ring is a single
  symmetric spin reused for every view direction: **32 poses**, a full turn
  about +Y. Build it roughly **4-fold symmetric**. (+68 rider slots, default 16
  seats.)
- **`ferris_wheel`** — a 1x4 vertical wheel. It is *not* vertically symmetric, so
  the engine stores **4 directions × 8 poses** (`base + direction*8 + frame`).
  The A-frame legs are base-game graphics, so the object provides only the
  rotating wheel and its gondolas (which orbit but stay upright); the 8 poses
  span one gondola spacing so an 8-fold wheel loops seamlessly. (+512 rider
  slots, default 32 seats.)
- **`twist`** — a 3x3 spinning platform (a thrill ride). Like the carousel it is
  one symmetric ring the engine reuses for every view (`base + frame % 24`), so
  build it roughly **4-fold symmetric** and keyframe a full turn about +Y in
  **24 poses**. (+216 rider slots, default 18 seats.)
- **`enterprise`** — a 4x4 wheel of enclosed pods (a thrill ride). The pods are
  *rigidly attached* and rotate with the wheel (riders invert), unlike the ferris
  wheel's upright gondolas, so the whole structure is one rigid spin. It is not
  symmetric, so the engine stores **4 directions × 49 poses interleaved**
  (`base + (frame << 2) + direction`); keyframe a full turn about the axle. The
  truss supports are base-game graphics, so the object provides only the wheel.
  (+48 rider slots, default 16 seats.)
- **`motion_simulator`** — a 2x2 enclosed pod that pitches and rolls (a thrill
  ride). The engine cycles the pod through a fixed buck-and-roll sequence rather
  than a steady spin, storing **4 directions × 35 poses interleaved**
  (`base + direction + frame*4`); keyframe the pitch/roll (frames 0–3 are the
  level restraint-load stages, 4–34 the motion). The boarding stairs are
  base-game graphics, so the object provides only the pod. (No rider slots,
  default 8 seats.)
- **`swinging_ship`** — a 1x5 pirate boat that swings on an A-frame (a thrill
  ride). The engine stores **2 camera planes × 19 swing blocks** (block 0
  upright, 1–9 leaning one way, 10–18 the other; `base + plane*9 + swing*18`),
  each ship sprite trailed by 8 (blank) rider slots. The A-frame supports are
  base-game graphics, so the object provides only the ship. In Blender you
  keyframe a natural back-and-forth swing and the add-on samples it into the 19
  block poses; a CLI config lists the 19 poses in block order. (Default 16 seats.)
- **`space_rings`** — a 3x3 ride of tumbling rings (a gentle ride). The object
  provides **one** ring (4 directions × 88 spin poses, `base + direction +
  frame*4`); the engine spawns four of them across the footprint
  (`carsPerFlatRide` 4). Keyframe one ring's full tumble about its axle; 4×88
  blank rider overlays follow. (1 seat per ring.)

> The example meshes are placeholders sized to render cleanly; rides that reuse
> base-game graphics — the ferris wheel's A-frame axle, the motion simulator's
> boarding stairs — must line up with those sprites, which is best checked
> in-game.

### CLI Quickstart

```bash
uv sync

# Quick per-view render of an example, written to test/. Fast iteration.
uv run openrct2-ride-generator --test examples/cli/stall/balloon.yaml

# Full render: writes object/ and <id>.parkobj in the output directory.
uv run openrct2-ride-generator examples/cli/stall/toilets.yaml

# 3x3 building flat ride (circus tent).
uv run openrct2-ride-generator examples/cli/building/circus.yaml

# Animated flat ride: 32-frame carousel spin (renders all 32 frames to test/).
uv run openrct2-ride-generator --test examples/cli/building/merry_go_round.yaml

# Animated flat ride: ferris wheel (4 directions x 8 frames to test/).
uv run openrct2-ride-generator --test examples/cli/building/ferris_wheel.yaml

# Animated flat ride: twist (24-frame symmetric spin to test/).
uv run openrct2-ride-generator --test examples/cli/building/twist.yaml

# Animated flat ride: enterprise (4 directions x 49 frames to test/).
uv run openrct2-ride-generator --test examples/cli/building/enterprise.yaml
```

The `examples/cli/` tree carries a worked example for every ride type: shops
(`burger_bar`, `drinks_stand`, `souvenir_shop`, `information_kiosk`, `balloon`,
`cash_machine`), facilities (`toilets`, `first_aid`), the 3x3 building rides
(`crooked_house`, `haunted_house`, `circus`), and the animated flat rides
(`merry_go_round`, `ferris_wheel`, `twist`, `enterprise`). The example meshes are
regenerated by `scripts/gen_example_meshes.py` (which also emits the flat rides'
`animation.frames` via `--print-spin`).

Install the resulting `.parkobj` into OpenRCT2's `object/` directory and
**restart** the game (it doesn't hot-reload objects).

## Mesh convention

OBJ meshes use **+X = forward**, **+Y = up**, **+Z = right**, with one tile =
`TILE_SIZE` units and the building centred on the tile. Materials are
classified by **name** (`Remap1`/`Remap2`/`Remap3` for colour remap regions).

**Facilities (toilets / first aid) must be authored with the door facing
OBJ +X** (the same +X axis in Blender), with the doorway (door + frame) as a
separate marked mesh: give the object the **Door** role in Blender, or mark
its placement `door: true` in a config (see
`examples/cli/stall/toilets.yaml`). The engine paints the doorway as its own
sprite at two view directions and the building body on top of it, so the
generator cuts the full-building render into vanilla-style column strips at
the doorway's screen extent — guests sort into the doorway and the strips
tile back together exactly. `facility_door_split: false` disables the split.
The anchoring rules are documented inline in
`openrct2_ride_generator/sprite_renderer.py`.

## License

GPL-3.0-or-later
