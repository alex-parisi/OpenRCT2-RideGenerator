# OpenRCT2 Ride Generator

A modern Blender add-on to author and export OpenRCT2 **stall and facility ride
objects** (food/drink stalls, shops, balloon stalls, information kiosks,
toilets, and first aid rooms) from 3D meshes. Geometry is ray-traced into the
isometric sprite sheets OpenRCT2 expects and packaged as a ready-to-install
`.parkobj`.

Rendering is handled by the external [`openrct2-x7-renderer`](https://pypi.org/project/openrct2-x7-renderer/)
package (an Embree-backed ray tracer shipping prebuilt, vendored wheels).

Flat rides (merry-go-round, ferris wheel, …) are out of scope for now; their
sprite layouts are bespoke per ride type and may be added later.

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
| `toilets`           | facility | 6            |
| `first_aid`         | facility | 6            |

### CLI Quickstart

```bash
uv sync

# Quick per-view render of an example, written to test/. Fast iteration.
uv run openrct2-ride-generator --test examples/cli/stall/balloon.yaml

# Full render: writes object/ and <id>.parkobj in the output directory.
uv run openrct2-ride-generator examples/cli/stall/toilets.yaml
```

Install the resulting `.parkobj` into OpenRCT2's `object/` directory and
**restart** the game (it doesn't hot-reload objects).

## Mesh convention

OBJ meshes use **+X = forward**, **+Y = up**, **+Z = right**, with one tile =
`TILE_SIZE` units and the building centred on the tile. Materials are
classified by **name** (`Remap1`/`Remap2`/`Remap3` for colour remap regions).

**Facilities (toilets / first aid) must be authored with the door facing
OBJ +X** (the same +X axis in Blender): the engine draws the door wall as a
separate sprite at two view directions so guests sort into the doorway, and the
generator splits the mesh along that edge (`facility_door_split: false`
disables the split). The anchoring rules are documented inline in
`openrct2_ride_generator/sprite_renderer.py`.

## License

GPL-3.0-or-later
