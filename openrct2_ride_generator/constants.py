"""
Stall-specific constants.
Shared rendering constants live in openrct2_x7_renderer.constants.
"""

from enum import Enum, auto

from openrct2_x7_renderer.constants import TILE_SIZE as TILE_SIZE  # noqa: F401


class StallKind(Enum):
    """How the engine paints the ride type: Shop.cpp (4 view sprites),
    Facility.cpp (6: door wall + body split at directions 1/2), or a 3x3
    building flat ride (CrookedHouse/HauntedHouse/Circus.cpp: one whole-building
    sprite per view direction, anchored at the centre tile)."""

    SHOP = auto()
    FACILITY = auto()
    BUILDING = auto()


# The ride types whose sprites come from the object. The engine synthesizes
# the car entry for shops/facilities (no "cars" block); the 3x3 building rides
# carry one invisible car whose base_image_id the track painter reads.
STALL_TYPES: dict[str, StallKind] = {
    "food_stall": StallKind.SHOP,
    "drink_stall": StallKind.SHOP,
    "shop": StallKind.SHOP,
    "balloon_stall": StallKind.SHOP,
    "information_kiosk": StallKind.SHOP,
    "toilets": StallKind.FACILITY,
    "first_aid": StallKind.FACILITY,
    "crooked_house": StallKind.BUILDING,
    "haunted_house": StallKind.BUILDING,
    "circus": StallKind.BUILDING,
}

# Per-type default `clearance` (OpenRCT2 world-Z units), from the bundled
# RCT2 stall objects; building rides use the RideTypeDescriptor's
# ClearanceHeight (ride/rtd/gentle/*.h).
DEFAULT_CLEARANCE: dict[str, int] = {
    "food_stall": 64,
    "drink_stall": 64,
    "shop": 56,
    "balloon_stall": 56,
    "information_kiosk": 48,
    "toilets": 32,
    "first_aid": 48,
    "crooked_house": 96,
    "haunted_house": 160,
    "circus": 128,
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

# OpenRCT2's 32 remap colour names, by palette index.
COLOR_NAMES = [
    "black",
    "grey",
    "white",
    "dark_purple",
    "light_purple",
    "bright_purple",
    "dark_blue",
    "light_blue",
    "icy_blue",
    "teal",
    "aquamarine",
    "saturated_green",
    "dark_green",
    "moss_green",
    "bright_green",
    "olive_green",
    "dark_olive_green",
    "bright_yellow",
    "yellow",
    "dark_yellow",
    "light_orange",
    "dark_orange",
    "light_brown",
    "saturated_brown",
    "dark_brown",
    "salmon_pink",
    "bordeaux_red",
    "saturated_red",
    "bright_red",
    "dark_pink",
    "bright_pink",
    "light_pink",
]

# A ride object's car images start at images_offset + kMaxRideTypesPerRideEntry,
# so three preview slots precede the view sprites.
PREVIEW_SLOTS = 3

# Shop.cpp paints base_image_id + direction: one sprite per view direction.
SHOP_VIEW_SPRITES = 4

# Facility.cpp uses base + ((direction + 2) & 3) plus two body overlays
# (indices +4 at direction 2 and +2 at direction 1).
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

# A facility's door wall is the slab Facility.cpp paints with a {28, 8} bound
# box (8 of 32 world units deep, +2 margin): faces within this fraction of a
# tile from the door edge belong to the door-wall sprite.
FACILITY_DOOR_BAND_FRACTION = 10.0 / 32.0

# The ride build-menu preview box is 112x112 pixels.
PREVIEW_BOX = 112
