"""
Usage:
    openrct2-ride-generator [--test|--skip-render] <input.json|.yaml>
    python -m openrct2_ride_generator [--test|--skip-render] <input.json|.yaml>
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from openrct2_object_common.cli import make_context, output_directory_of, run_cli
from openrct2_x7_renderer.types import Light

from .exporter import export_stall, export_stall_test
from .loader import load_stall, object_type_of


class _RideObject(Protocol):
    """The common surface the CLI needs from a loaded ride object."""

    units_per_tile: float


_Loader = Callable[[Path], _RideObject]
_Exporter = Callable[..., None]

# object_type -> (load, export, export_test); flat rides slot in beside "ride"
# later.
_DISPATCH: dict[str, tuple[_Loader, _Exporter, _Exporter]] = {
    "ride": (load_stall, export_stall, export_stall_test),
}


def _render(args: argparse.Namespace, root: dict[str, Any], lights: list[Light]) -> None:
    load, export, export_test = _DISPATCH[object_type_of(root)]
    obj = load(args.input)
    context = make_context(lights, obj.units_per_tile, args.test, root)
    if args.test:
        export_test(obj, context)
    else:
        export(obj, context, output_directory_of(root), skip_render=args.skip_render)


def main(argv: list[str] | None = None) -> int:
    return run_cli("openrct2-ride-generator", argv, _render)


if __name__ == "__main__":
    sys.exit(main())
