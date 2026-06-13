"""
Stall dataclass.
Rendering primitives come from openrct2_x7_renderer.types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from openrct2_x7_renderer.constants import TILE_SIZE
from openrct2_x7_renderer.types import IndexedImage, Model

if TYPE_CHECKING:
    from openrct2_x7_renderer.mesh import Mesh

from .constants import (
    BUILDING_VIEW_SPRITES,
    FACILITY_VIEW_SPRITES,
    HAUNTED_HOUSE_OVERLAY_SPRITES,
    PREVIEW_SLOTS,
    SHOP_VIEW_SPRITES,
    STALL_TYPES,
    StallKind,
)


@dataclass
class Stall:
    id: str = ""
    original_id: str = ""
    name: str = ""
    description: str = ""
    authors: list[str] = field(default_factory=list)
    version: str = "1.0"

    units_per_tile: float = TILE_SIZE

    stall_type: str = "food_stall"
    sells: list[str] = field(default_factory=list)
    clearance: int = 0
    disable_painting: bool = True
    # Colour presets, each a [main, additional1, additional2] triple of
    # COLOR_NAMES entries.
    car_colours: list[list[str]] = field(default_factory=lambda: [["black", "black", "black"]])
    build_menu_priority: int = 0

    # Building rides only: the car's numSeats (= ride capacity).
    num_seats: int = 0

    # Escape hatch: render the full building into the facility's directional
    # slots and leave the body overlays blank (peeps then draw in front of the
    # whole building at directions 1/2 instead of inside it).
    facility_door_split: bool = True

    # Geometry
    meshes: list[Mesh] = field(default_factory=list)
    model: Model = field(default_factory=Model)
    # The `door: true` subset of `model` (the facility doorway placements);
    # its rendered screen extent cuts the door sprite out of the full building.
    door_model: Model = field(default_factory=Model)

    preview: IndexedImage | None = None

    @property
    def kind(self) -> StallKind:
        return STALL_TYPES[self.stall_type]

    @property
    def num_view_sprites(self) -> int:
        if self.kind is StallKind.FACILITY:
            return FACILITY_VIEW_SPRITES
        if self.kind is StallKind.BUILDING:
            return BUILDING_VIEW_SPRITES
        return SHOP_VIEW_SPRITES

    @property
    def num_overlay_sprites(self) -> int:
        """Animation overlays after the view sprites (haunted house ghosts)."""
        if self.stall_type == "haunted_house":
            return HAUNTED_HOUSE_OVERLAY_SPRITES
        return 0

    @property
    def num_sprites(self) -> int:
        return PREVIEW_SLOTS + self.num_view_sprites + self.num_overlay_sprites
