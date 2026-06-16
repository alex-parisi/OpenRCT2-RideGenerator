"""
Stall-specific constants.
Shared rendering constants live in openrct2_x7_renderer.constants.
"""

from dataclasses import dataclass
from enum import Enum, auto

from openrct2_object_common.colours import COLOR_NAMES as COLOR_NAMES  # noqa: F401
from openrct2_x7_renderer.constants import TILE_SIZE as TILE_SIZE  # noqa: F401


class StallKind(Enum):
    """How the engine paints the ride type: Shop.cpp (4 view sprites),
    Facility.cpp (6: door wall + body split at directions 1/2), a 3x3
    building flat ride (CrookedHouse/HauntedHouse/Circus.cpp: one whole-building
    sprite per view direction, anchored at the centre tile), or an *animated*
    3x3 flat ride (MerryGoRound.cpp etc.: a vehicle-drawn structure with a ring
    of rotation frames the engine cycles to spin it)."""

    SHOP = auto()
    FACILITY = auto()
    BUILDING = auto()
    FLAT_RIDE = auto()


# The ride types whose sprites come from the object. The engine synthesizes
# the car entry for shops/facilities (no "cars" block); the 3x3 building rides
# carry one invisible car whose base_image_id the track painter reads.
STALL_TYPES: dict[str, StallKind] = {
    "food_stall": StallKind.SHOP,
    "drink_stall": StallKind.SHOP,
    "shop": StallKind.SHOP,
    "balloon_stall": StallKind.SHOP,
    "information_kiosk": StallKind.SHOP,
    "cash_machine": StallKind.SHOP,
    "toilets": StallKind.FACILITY,
    "first_aid": StallKind.FACILITY,
    "crooked_house": StallKind.BUILDING,
    "haunted_house": StallKind.BUILDING,
    "circus": StallKind.BUILDING,
    "merry_go_round": StallKind.FLAT_RIDE,
    "ferris_wheel": StallKind.FLAT_RIDE,
}

# Shop-kind ride types whose object may carry a `sells` shop item. The cash
# machine paints like a shop (TrackStyle::shop, 4 views) but dispenses cash and
# never sells a shop item, so it is a SHOP that is *not* in this set.
SHOP_SELL_TYPES = frozenset(
    {"food_stall", "drink_stall", "shop", "balloon_stall", "information_kiosk"}
)

# Per-type default `clearance` (OpenRCT2 world-Z units), from the bundled
# RCT2 stall objects; building rides use the RideTypeDescriptor's
# ClearanceHeight (ride/rtd/gentle/*.h).
DEFAULT_CLEARANCE: dict[str, int] = {
    "food_stall": 64,
    "drink_stall": 64,
    "shop": 56,
    "balloon_stall": 56,
    "information_kiosk": 48,
    "cash_machine": 64,
    "toilets": 32,
    "first_aid": 48,
    "crooked_house": 96,
    "haunted_house": 160,
    "circus": 128,
    "merry_go_round": 64,
    "ferris_wheel": 176,
}

# OpenRCT2's ShopItemLookupTable (object/RideObject.cpp): the valid `sells`
# strings.
SHOP_ITEMS = frozenset(
    {
        "burger",
        "chips",
        "ice_cream",
        "candyfloss",
        "pizza",
        "popcorn",
        "hot_dog",
        "tentacle",
        "toffee_apple",
        "doughnut",
        "chicken",
        "pretzel",
        "funnel_cake",
        "beef_noodles",
        "fried_rice_noodles",
        "wonton_soup",
        "meatball_soup",
        "sub_sandwich",
        "cookie",
        "roast_sausage",
        "drink",
        "coffee",
        "lemonade",
        "chocolate",
        "iced_tea",
        "fruit_juice",
        "soybean_milk",
        "sujeonggwa",
        "balloon",
        "toy",
        "map",
        "photo",
        "umbrella",
        "voucher",
        "hat",
        "tshirt",
        "sunglasses",
    }
)

# kMaxShopItemsPerRideEntry: the engine reads at most two `sells` entries.
MAX_SELLS = 2

# A ride object's car images start at images_offset + kMaxRideTypesPerRideEntry,
# so three preview slots precede the view sprites.
PREVIEW_SLOTS = 3

# Shop.cpp paints base_image_id + direction: one sprite per view direction.
SHOP_VIEW_SPRITES = 4

# Facility.cpp uses base + ((direction + 2) & 3) plus two body overlays
# (indices +4 at direction 2 and +2 at direction 1, painted over the door
# sprite: their top-slab bound box sorts above the door wall's).
FACILITY_VIEW_SPRITES = 6

# The 3x3 building painters (CrookedHouse/HauntedHouse/Circus.cpp) paint
# base_image_id + direction: one whole-building sprite per view direction,
# anchored at the centre tile's reference corner.
BUILDING_VIEW_SPRITES = 4

# A 3x3 building ride occupies 3 tiles per side, centred on the middle tile.
BUILDING_FOOTPRINT_TILES = 3

# HauntedHouse.cpp paints ghost overlays as base + 3 + direction * 18 + frame
# with frame in 1..18, i.e. 72 extra images after the 4 building views.
HAUNTED_HOUSE_FRAMES_PER_DIRECTION = 18
HAUNTED_HOUSE_OVERLAY_SPRITES = 4 * HAUNTED_HOUSE_FRAMES_PER_DIRECTION

# Default car numSeats (= ride capacity), from the bundled RCT2 objects
# (CHBUILD / HHBUILD / CIRCUS1).
DEFAULT_NUM_SEATS: dict[str, int] = {
    "crooked_house": 5,
    "haunted_house": 15,
    "circus": 30,
    "merry_go_round": 16,
    "ferris_wheel": 32,
}

# The fixed car entry the bundled RCT2 building rides share. The car is never
# drawn as a vehicle (the track painter reads base_image_id directly) and
# recalculateSpriteBounds trues up the nominal sprite bounds, so these values
# are emitted verbatim.
BUILDING_CAR_ENTRY: dict[str, object] = {
    "spacing": 139456,
    "mass": 3000,
    "seatsInPairs": False,
    "spriteWidth": 55,
    "spriteHeightNegative": 150,
    "spriteHeightPositive": 28,
    "carVisual": 1,
    "drawOrder": 6,
    "frames": {"flat": True},
    "recalculateSpriteBounds": True,
    "numSegments": 0,
}

# Crooked house guests just walk in; haunted house and circus share this
# 16-entry loading-waypoint table (3 [x, y] stops per station direction
# variant), copied from HHBUILD / CIRCUS1.
BUILDING_TYPES_WITH_WAYPOINTS = frozenset({"haunted_house", "circus"})

LOADING_WAYPOINTS: list[list[list[int]]] = [
    [[40, 40], [-40, 40], [-36, 0]],
    [[-40, -40], [-36, 0], [-36, 0]],
    [[-36, 0], [-36, 0], [-36, 0]],
    [[-40, 40], [-36, 0], [-36, 0]],
    [[40, 40], [0, 36], [0, 36]],
    [[40, -40], [40, 40], [0, 36]],
    [[-40, 40], [0, 36], [0, 36]],
    [[0, 36], [0, 36], [0, 36]],
    [[36, 0], [36, 0], [36, 0]],
    [[40, -40], [36, 0], [36, 0]],
    [[-40, -40], [40, -40], [36, 0]],
    [[40, 40], [36, 0], [36, 0]],
    [[40, -40], [0, -36], [0, -36]],
    [[0, -36], [0, -36], [0, -36]],
    [[-40, -40], [0, -36], [0, -36]],
    [[-40, 40], [-40, -40], [0, -36]],
]

# ── Animated flat rides ───────────────────────────────────────────────────────
# An animated flat ride draws its structure as a *vehicle* sprite the engine
# spins by cycling a ring of rotation frames. The exact image layout differs per
# ride, so each carries a FlatRideSpec:
#
#   * merry_go_round (MerryGoRound.cpp) reads
#     `base + (animationFrame & rotationFrameMask)`; the camera rotation folds in
#     as a multiple of (mask + 1) and cancels, so the carousel is ONE ring of 32
#     frames rendered from a single view and reused for all 4 directions.
#   * ferris_wheel (FerrisWheel.cpp) reads `base + direction * 8 + animationFrame`
#     -- the wheel is *not* vertically symmetric, so the ring is 4 directions x 8
#     frames. The A-frame supports are base-game graphics (sprite 22150), so the
#     object provides only the rotating wheel + gondolas.
#
# In both, the author keyframes the spin in Blender and the add-on samples it
# into `frames` poses; the trailing `rider_slots` peep overlays are emitted blank
# (like the haunted house's ghosts) so the ride runs without a stray rider.


@dataclass(frozen=True)
class FlatRideSpec:
    """Engine sprite layout + fixed car-entry fields for an animated flat ride."""

    frames: int  # authored animation poses per direction (= rotationFrameMask + 1)
    directions: int  # distinct view directions stored in the structure ring
    rider_slots: int  # trailing blank peep overlays after the structure frames
    has_shelter: bool  # the ride's `hasShelter` property
    waypoints: list[list[list[int]]]  # car loadingWaypoints
    car: dict[str, object]  # fixed car-entry fields (sans numSeats / colour flags)

    @property
    def structure_sprites(self) -> int:
        """Rendered structure images: one per (direction, frame)."""
        return self.directions * self.frames


# The merry-go-round's 64-entry loading-waypoint table (3 [x, y] stops per
# station direction variant), copied verbatim from MGR1.
MERRY_GO_ROUND_WAYPOINTS: list[list[list[int]]] = [
    [[43, 43], [-43, 43], [-42, 3]],
    [[-43, -43], [-42, 3], [-42, 3]],
    [[-42, 3], [-42, 3], [-42, 3]],
    [[-43, 43], [-42, 3], [-42, 3]],
    [[43, -43], [-43, -43], [-42, -3]],
    [[-43, -43], [-42, -3], [-42, -3]],
    [[-42, -3], [-42, -3], [-42, -3]],
    [[-43, 43], [-42, -3], [-42, -3]],
    [[43, 43], [3, 42], [3, 42]],
    [[43, -43], [43, 43], [3, 42]],
    [[-43, 43], [3, 42], [3, 42]],
    [[3, 42], [3, 42], [3, 42]],
    [[43, 43], [-3, 42], [-3, 42]],
    [[-43, -43], [-43, 43], [-3, 42]],
    [[-43, 43], [-3, 42], [-3, 42]],
    [[-3, 42], [-3, 42], [-3, 42]],
    [[42, -3], [42, -3], [42, -3]],
    [[43, -43], [42, -3], [42, -3]],
    [[-43, -43], [43, -43], [42, -3]],
    [[43, 43], [42, -3], [42, -3]],
    [[42, 3], [42, 3], [42, 3]],
    [[43, -43], [42, 3], [42, 3]],
    [[-43, 43], [43, 43], [42, 3]],
    [[43, 43], [42, 3], [42, 3]],
    [[43, -43], [-3, -42], [-3, -42]],
    [[-3, -42], [-3, -42], [-3, -42]],
    [[-43, -43], [-3, -42], [-3, -42]],
    [[-43, 43], [-43, -43], [-3, -42]],
    [[43, -43], [3, -42], [3, -42]],
    [[3, -42], [3, -42], [3, -42]],
    [[-43, -43], [3, -42], [3, -42]],
    [[43, 43], [43, -43], [3, -42]],
    [[43, 43], [-43, 43], [-33, 31]],
    [[-43, -43], [-43, 43], [-33, 31]],
    [[-43, 43], [-43, 43], [-33, 31]],
    [[-43, 43], [-43, 43], [-33, 31]],
    [[43, 43], [-43, 43], [-31, 33]],
    [[-43, -43], [-43, 43], [-31, 33]],
    [[-43, 43], [-43, 43], [-31, 33]],
    [[-43, 43], [-43, 43], [-31, 33]],
    [[43, 43], [43, 43], [33, 31]],
    [[43, -43], [43, 43], [33, 31]],
    [[-43, 43], [43, 43], [33, 31]],
    [[43, 43], [43, 43], [33, 31]],
    [[43, 43], [43, 43], [31, 33]],
    [[43, -43], [43, 43], [31, 33]],
    [[-43, 43], [43, 43], [31, 33]],
    [[43, 43], [43, 43], [31, 33]],
    [[43, -43], [43, -43], [33, -31]],
    [[43, -43], [43, -43], [33, -31]],
    [[-43, -43], [43, -43], [33, -31]],
    [[43, 43], [43, -43], [33, -31]],
    [[43, -43], [43, -43], [31, -33]],
    [[43, -43], [43, -43], [31, -33]],
    [[-43, -43], [43, -43], [31, -33]],
    [[43, 43], [43, -43], [31, -33]],
    [[43, -43], [-43, -43], [-33, -31]],
    [[-43, -43], [-43, -43], [-33, -31]],
    [[-43, -43], [-43, -43], [-33, -31]],
    [[-43, 43], [-43, -43], [-33, -31]],
    [[43, -43], [-43, -43], [-31, -33]],
    [[-43, -43], [-43, -43], [-31, -33]],
    [[-43, -43], [-43, -43], [-31, -33]],
    [[-43, 43], [-43, -43], [-31, -33]],
]

# The ferris wheel's 16-entry loading-waypoint table, copied verbatim from FWH1.
FERRIS_WHEEL_WAYPOINTS: list[list[list[int]]] = [
    [[44, -12], [-16, -12], [-16, -12]],
    [[-16, -12], [-16, -12], [-16, -12]],
    [[-76, -12], [-16, -12], [-16, -12]],
    [[-16, 12], [-16, 12], [-16, 12]],
    [[12, 16], [12, 16], [12, 16]],
    [[12, -44], [12, 16], [12, 16]],
    [[-12, 16], [-12, 16], [-12, 16]],
    [[12, 76], [12, 16], [12, 16]],
    [[76, -12], [16, -12], [16, -12]],
    [[16, -12], [16, -12], [16, -12]],
    [[-44, -12], [16, -12], [16, -12]],
    [[16, 12], [16, 12], [16, 12]],
    [[12, -16], [12, -16], [12, -16]],
    [[12, -76], [12, -16], [12, -16]],
    [[-12, -16], [-12, -16], [-12, -16]],
    [[-12, 44], [-12, -16], [-12, -16]],
]

# Fixed car-entry fields per ride (numSeats and the remap-derived colour flags
# are added by the exporter). The car is never drawn as a normal vehicle, and
# recalculateSpriteBounds trues up the nominal bounds, so these are emitted
# verbatim. `rotationFrameMask` = frames - 1.
_MGR_CAR: dict[str, object] = {
    "rotationFrameMask": 31,
    "spacing": 139456,
    "mass": 200,
    "tabOffset": -24,
    "spriteWidth": 55,
    "spriteHeightNegative": 72,
    "spriteHeightPositive": 28,
    "carVisual": 1,
    "drawOrder": 6,
    "frames": {"flat": True},
    "recalculateSpriteBounds": True,
    "numSegments": 4,
}
_FWH_CAR: dict[str, object] = {
    "rotationFrameMask": 7,
    "spacing": 139456,
    "mass": 3000,
    "spriteWidth": 87,
    "spriteHeightNegative": 170,
    "spriteHeightPositive": 37,
    "carVisual": 1,
    "drawOrder": 6,
    "frames": {"flat": True},
    "recalculateSpriteBounds": True,
    "numSegments": 0,
}

FLAT_RIDE_SPECS: dict[str, FlatRideSpec] = {
    "merry_go_round": FlatRideSpec(
        frames=32, directions=1, rider_slots=68, has_shelter=True,
        waypoints=MERRY_GO_ROUND_WAYPOINTS, car=_MGR_CAR,
    ),
    "ferris_wheel": FlatRideSpec(
        frames=8, directions=4, rider_slots=512, has_shelter=False,
        waypoints=FERRIS_WHEEL_WAYPOINTS, car=_FWH_CAR,
    ),
}

# The ride build-menu preview box is 112x112 pixels.
PREVIEW_BOX = 112
