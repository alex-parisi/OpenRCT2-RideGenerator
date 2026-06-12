"""
OpenRCT2 ride object generator (stalls and facilities).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("OpenRCT2-RideGenerator")
except PackageNotFoundError:  # pragma: no cover - source tree without an install
    __version__ = "0.0.0"
