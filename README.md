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
ring; in a CLI config, list one pose per frame under `animation.frames`. Each
ride carries **rider slots** the engine draws over the structure; `seats` sets
capacity. The rider slots are emitted blank (like the haunted house's ghosts)
unless the object supplies riders — see [Riders](#riders) below (every flat ride
but the enclosed motion simulator ships visible riders today). Four layouts ship
today:

- **`merry_go_round`** — a 3x3 carousel, centred on the middle tile. The engine
  folds the camera rotation out (`rotationOffset & 0x1F`), so the ring is a single
  symmetric spin reused for every view direction, and it **loops the 32 poses four
  times per revolution** while the riders sweep the full turn. Build it **4-fold
  symmetric** and make the **32 poses span one quarter turn (90°)** about +Y — a
  full turn baked into the 32 poses would spin the structure 4× too fast relative
  to its riders. (+68 rider slots — one seat's pair on the front-visible arc;
  default 16 seats.)
- **`ferris_wheel`** — a 1x4 vertical wheel. It is *not* vertically symmetric, so
  the engine stores **4 directions × 8 poses** (`base + direction*8 + frame`).
  The A-frame legs are base-game graphics, so the object provides only the
  rotating wheel and its gondolas (which orbit but stay upright); the 8 poses
  span one gondola spacing so an 8-fold wheel loops seamlessly. (+512 rider slots
  — one gondola's pair orbiting the axle, 4 directions × 128; default 32 seats.)
- **`twist`** — a 3x3 spinning platform of cups (a thrill ride). Like the carousel
  it is one symmetric ring the engine reuses for every view (`base + frameNum %
  24`), and it **loops the 24 poses nine times per revolution** while the 216 rider
  overlays sweep the full turn. Build it **9-fold symmetric** (nine cups) and make
  the **24 poses span one cup spacing (40°)** about +Y — a full turn baked into the
  24 poses would spin the cups 9× too fast relative to the riders in them.
  (+216 rider slots, default 18 seats.)
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
  each ship sprite trailed by 8 rider slots (the bench rows). The A-frame supports are
  base-game graphics, so the object provides only the ship. In Blender you
  keyframe a natural back-and-forth swing and the add-on samples it into the 19
  block poses; a CLI config lists the 19 poses in block order. (Default 16 seats.)
- **`space_rings`** — a 3x3 ride of tumbling rings (a gentle ride). The object
  provides **one** ring (4 directions × 88 spin poses, `base + direction +
  frame*4`); the engine spawns four of them across the footprint
  (`carsPerFlatRide` 4). Keyframe one ring's full tumble about its axle; the
  rider tumbles with it (4×88 rider overlays). (1 seat per ring.)

> The example meshes are placeholders sized to render cleanly; rides that reuse
> base-game graphics — the ferris wheel's A-frame axle, the motion simulator's
> boarding stairs — must line up with those sprites, which is best checked
> in-game.

### Riders

An animated flat ride can carry **visible riders**: seated peeps the engine draws
over the spinning structure and recolours **per rider** by each peep's t-shirt
colour. Give a rider's shirt **`Remap1`** and (for a pair) the second shirt
**`Remap2`** (the engine passes the peep colours as the image's primary and
secondary remap), then:

- **In Blender** — model the rider on a seat, parent it into the spinning
  structure, and give it the **Rider** role. It animates with the spin you
  already keyframe; the add-on samples it into the ride's rider slots. (The
  swinging ship wants one Rider object per bench row, assigned to sub-slots in
  name order.)
- **In a CLI config** — add a `rider_animation.frames` list beside
  `animation.frames` (or, for the swinging ship, a `rider_rows` list of bench
  rows), referencing the rider mesh(es).
  `scripts/gen_example_meshes.py --print-riders <ride>` emits the block (see the
  worked example for each ride below).

The rider layout is the engine's, so each ride has a fixed shape:

| `ride_type`      | Riders                                                  |
|------------------|---------------------------------------------------------|
| `merry_go_round` | **68** poses — one seat's pair on the front-visible arc (ring positions 13–80 of 128), rotating about +Y with the platform; single view. |
| `ferris_wheel`   | **4 × 128** poses — one gondola's pair orbiting the axle **upright**, per view direction. |
| `twist`          | **216** poses — one seat's pair at 216 rotation phases of the full turn, single view. |
| `enterprise`     | **48** poses — a single rider in an enclosed pod, shown only near the bottom (3 sub-frames × 16 folded angles), single view; `Remap1` only. |
| `space_rings`    | **4 × 88** poses — one rider tumbling **with** the ring (shirt `Remap1`, trousers `Remap2`), the same ring as the structure. |
| `swinging_ship`  | **8 bench rows** of rider-pairs *interleaved* after each ship sprite (2 planes × 19 swings), each swinging with the ship. |

The motion simulator's pod is enclosed, so it has no riders. Riders reuse the
same per-ride conventions as base-game sprites (orbit phase, seat radius, the
enterprise's folded angles), so their exact alignment is best checked in-game.

### Animating in Blender

Each ride type has a fixed **animation style** the engine expects, and the add-on
only *samples* the motion you keyframe into that style — it does not invent motion.
So an animator has to keyframe the right kind of motion for the chosen ride, and a
handful of quirks bite if you don't. The rules that apply to every flat ride:

- **Keyframe exactly one clean loop over the scene frame range.** The add-on
  samples `frame_start … frame_end` into the ride's pose count, so the first and
  last frames are the same instant of a seamless cycle. Author one full turn (or
  one full swing/tumble), not several.
- **Use Linear interpolation for the cycle** (no ease-in/ease-out). The engine
  plays the sampled poses back at its **own constant speed**; Bezier easing bakes
  a speed-up/slow-down into the poses, which reads in-game as a stutter or even a
  reversal. You set the *poses*, the engine sets the *timing*.
- **Don't model the base-game parts.** Several rides reuse vanilla graphics for
  their fixed structure — the ferris wheel's A-frame legs, the enterprise's truss,
  the motion simulator's boarding stairs, the swinging ship's A-frame. Model only
  the moving piece; the static support is drawn by the engine and your part must
  line up with it (check in-game).
- **The single-view spinners must be rotationally symmetric.** `merry_go_round`
  and `twist` render *one* view that the engine reuses for all four camera angles,
  *and* it loops their structure ring several times per revolution (the carousel
  4×, the twist 9×) while the riders sweep the full turn. So the structure must be
  symmetric about the spin axis — the carousel **4-fold**, the twist **9-fold**
  (nine cups) — or it looks wrong from three camera angles and the loop stutters.
  You still keyframe one full turn; the add-on samples the structure over just its
  symmetry slice (90° / 40°) and the riders over the full turn for you. The
  four-direction rides don't have this constraint.
- **Model one rider unit; the engine replicates it.** Where a ride carries riders
  you author a *single* seat's rider-pair (or, for the swinging ship, one bench
  row) and give it the **Rider** role — the engine clones it around the ride. The
  twist is the classic trap: place nine riders and the engine clones each into
  nine, giving 81 peeps.

Per-ride quirks to keep in mind while animating:

| Ride               | Motion to keyframe                          | Watch out for |
|--------------------|---------------------------------------------|---------------|
| `merry_go_round`   | One full 360° turn about +Y.                 | Single view; must be **4-fold symmetric** (the add-on bakes the structure as a 90° slice). |
| `ferris_wheel`     | One full turn of the wheel about the axle.   | Gondolas orbit but stay **upright**; don't model the A-frame legs. |
| `twist`            | One full 360° turn about +Y.                 | Single view; must be **9-fold symmetric** (nine cups; the structure bakes as a 40° slice); use **one** rider-pair — the engine clones it into 9 (81 peeps if you place 9). |
| `enterprise`       | One full turn of the tilted wheel.           | Pods are **rigid**, so riders invert at the top; don't model the truss. |
| `motion_simulator` | The pod's **pitch/roll** — *not* a spin.     | Frames 0–3 are the level restraint-load pose (author a level pose at the very start of the timeline), then the buck-and-roll; no riders; don't model the stairs. |
| `swinging_ship`    | A natural **back-and-forth swing** — *not* a spin. | One Rider object per bench row, named in row order; don't model the A-frame. |
| `space_rings`      | One full **tumble** of a single ring about its axle. | The engine spawns four rings across the footprint; the rider tumbles with the ring. |

> Adding a flat ride? Keep this table, the `FLAT_RIDE_ANIM_HINTS` shown in the
> Blender N-panel (`ride_renderer_addon/props.py`), and the engine-mechanics
> bullets above in sync, so animators get the same guidance everywhere.

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

Each mesh has a **role**: *Geometry* (part of the model), *Door* (a facility
doorway, below), *Rider* (a flat ride's seated rider-pair, see
[Riders](#riders)), or *Ignore*. In Blender the role selector offers only the
roles that apply to the chosen ride type — *Door* for facilities, *Rider* for
the merry-go-round and ferris wheel.

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
