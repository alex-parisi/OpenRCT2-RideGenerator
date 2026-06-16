"""
Usage:
    openrct2-ride-generator [--test|--skip-render] <input.json|.yaml>
    python -m openrct2_ride_generator [--test|--skip-render] <input.json|.yaml>
"""

import sys

from openrct2_object_common.dispatch import Dispatch, run_dispatch_cli

from .exporter import export_stall, export_stall_test
from .loader import load_stall, object_type_of

# object_type -> (load, export, export_test); flat rides slot in beside "ride"
# later.
_DISPATCH: Dispatch = {
    "ride": (load_stall, export_stall, export_stall_test),
}


def main(argv: list[str] | None = None) -> int:
    return run_dispatch_cli("openrct2-ride-generator", argv, _DISPATCH, object_type_of)


if __name__ == "__main__":
    sys.exit(main())
