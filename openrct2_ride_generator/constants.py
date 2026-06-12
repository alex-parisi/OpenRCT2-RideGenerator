"""
Stall-specific constants.
Shared rendering constants live in openrct2_x7_renderer.constants.
"""

from enum import Enum, auto

from openrct2_x7_renderer.constants import TILE_SIZE as TILE_SIZE  # noqa: F401


class StallKind(Enum):
    """How the engine paints the ride type: Shop.cpp (4 view sprites) or
    Facility.cpp (6: door wall + body split at directions 1/2)."""

    SHOP = auto()
    FACILITY = auto()


# The shop/facility ride types whose sprites come from the object (the engine
# synthesizes their car entry, so the object.json needs no "cars" block).
STALL_TYPES: dict[str, StallKind] = {
    "food_stall": StallKind.SHOP,
    "drink_stall": StallKind.SHOP,
    "shop": StallKind.SHOP,
    "balloon_stall": StallKind.SHOP,
    "information_kiosk": StallKind.SHOP,
    "toilets": StallKind.FACILITY,
    "first_aid": StallKind.FACILITY,
}

# Per-type default `clearance` (OpenRCT2 world-Z units), from the bundled
# RCT2 stall objects.
DEFAULT_CLEARANCE: dict[str, int] = {
    "food_stall": 64,
    "drink_stall": 64,
    "shop": 56,
    "balloon_stall": 56,
    "information_kiosk": 48,
    "toilets": 32,
    "first_aid": 48,
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

# A facility's door wall is the slab Facility.cpp paints with a {28, 8} bound
# box (8 of 32 world units deep, +2 margin): faces within this fraction of a
# tile from the door edge belong to the door-wall sprite.
FACILITY_DOOR_BAND_FRACTION = 10.0 / 32.0

# The ride build-menu preview box is 112x112 pixels.
PREVIEW_BOX = 112
