"""
Stall-specific constants.
Shared rendering constants live in openrct2_x7_renderer.constants.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from openrct2_object_common.colours import COLOR_NAMES as COLOR_NAMES  # noqa: F401
from openrct2_x7_renderer.constants import TILE_SIZE as TILE_SIZE  # noqa: F401

from ._ride_metadata import RIDE_METADATA


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
    "3d_cinema": StallKind.BUILDING,
    "merry_go_round": StallKind.FLAT_RIDE,
    "ferris_wheel": StallKind.FLAT_RIDE,
    "twist": StallKind.FLAT_RIDE,
    "enterprise": StallKind.FLAT_RIDE,
    "motion_simulator": StallKind.FLAT_RIDE,
    "swinging_ship": StallKind.FLAT_RIDE,
    "space_rings": StallKind.FLAT_RIDE,
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
    "3d_cinema": 128,
    "merry_go_round": 64,
    "ferris_wheel": 176,
    "twist": 64,
    "enterprise": 160,
    "motion_simulator": 64,
    "swinging_ship": 112,
    "space_rings": 48,
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

# ── Per-ride-type metadata (cloned from the vanilla RCT2 objects) ──────────────
# The car-bearing ride types -- the 3x3 building rides and the animated flat
# rides -- clone a vanilla ride type, so their gameplay / packaging metadata
# matches that object: the fixed car-entry fields, the peep loading-waypoint
# table, the default capacity, the build-menu category and the shelter flag. The
# data is extracted from OpenRCT2's decoded RCT2 objects by
# scripts/extract_ride_metadata.py into the generated _ride_metadata module (so
# adding a ride type is a data refresh, not a hand-transcription of 60-entry
# waypoint arrays). The exporter fills in the per-object dynamic fields it omits:
# numSeats (capacity, overridable) and the remap-derived colour flags.


@dataclass(frozen=True)
class RideMeta:
    """Gameplay / packaging metadata for one car-bearing ride type."""

    category: str  # build-menu category ("gentle" / "thrill")
    has_shelter: bool  # the ride's `hasShelter` property
    default_seats: int  # car numSeats (= ride capacity) default
    cars_per_flat_ride: int  # `carsPerFlatRide` (rings/cars the engine spawns; 4 for space rings)
    car: dict[str, Any]  # fixed car-entry fields (sans numSeats / colour flags)
    waypoints: list[list[list[int]]] | None  # car loadingWaypoints, or None


# Crooked-house guests are swallowed straight into the building, so -- unlike the
# other 3x3 buildings -- its car emits no loading waypoints, even though the
# vanilla CHBUILD object carries the shared table. Suppress it here to match.
_NO_WAYPOINTS = frozenset({"crooked_house"})


def _ride_meta(ride_type: str, data: dict[str, Any]) -> RideMeta:
    raw_waypoints = data["waypoints"]
    waypoints = None if ride_type in _NO_WAYPOINTS else raw_waypoints
    return RideMeta(
        category=data["category"],
        has_shelter=data["has_shelter"],
        default_seats=data["default_seats"],
        cars_per_flat_ride=data["cars_per_flat_ride"],
        car=data["car"],
        waypoints=waypoints,
    )


RIDE_META: dict[str, RideMeta] = {
    ride_type: _ride_meta(ride_type, data) for ride_type, data in RIDE_METADATA.items()
}

# Default car numSeats (= ride capacity) per car-bearing ride type.
DEFAULT_NUM_SEATS: dict[str, int] = {t: m.default_seats for t, m in RIDE_META.items()}

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
    """Engine sprite layout for an animated flat ride. The gameplay / packaging
    metadata (car entry, waypoints, capacity, category, shelter) lives in
    RIDE_META, cloned from the vanilla object; this captures only what the
    painter dictates -- the structure ring's shape and image order."""

    frames: int  # authored animation poses per direction (carousel/ferris: rotationFrameMask + 1)
    directions: int  # distinct view directions stored in the structure ring
    rider_slots: int  # trailing blank peep overlays after the structure frames
    # The properties-level `rotationMode` (how the engine advances the structure's
    # animation frame). The carousel/ferris use a plain rotationFrameMask instead and
    # leave this unset; the twist (1) and enterprise (2) set it.
    rotation_mode: int | None = None
    # Image order of the structure ring. False (carousel/ferris): direction-major,
    # `image = direction * frames + frame` (FerrisWheel.cpp `base + direction*8 + frame`).
    # True (enterprise): direction-minor, `image = frame * directions + direction`
    # (Enterprise.cpp `base + (animationFrame << 2) + direction`).
    direction_minor: bool = False
    # Blank peep overlays emitted after *each* rendered structure image (vs the
    # trailing `rider_slots`). The swinging ship interleaves 8 rider sprites per
    # (plane, swing) structure sprite (SwingingShip.cpp `base + plane*9 + swing*18`,
    # rider = base + frameNum), so each rendered ship is followed by 8 blanks.
    blank_sub_slots: int = 0

    @property
    def structure_sprites(self) -> int:
        """Structure images the object provides: one rendered image per (direction,
        frame), each trailed by `blank_sub_slots` interleaved blanks."""
        return self.directions * self.frames * (1 + self.blank_sub_slots)


FLAT_RIDE_SPECS: dict[str, FlatRideSpec] = {
    "merry_go_round": FlatRideSpec(frames=32, directions=1, rider_slots=68),
    "ferris_wheel": FlatRideSpec(frames=8, directions=4, rider_slots=512),
    # Twist.cpp: `base + (frameNum % 24)`, one symmetric 24-frame spin reused for
    # every view direction (like the carousel), then 216 blank rider overlays.
    "twist": FlatRideSpec(frames=24, directions=1, rider_slots=216, rotation_mode=1),
    # Enterprise.cpp: `base + (animationFrame << 2) + direction`, a tilted wheel
    # stored as 4 directions x 49 frames interleaved (direction is the fast index),
    # then 48 blank rider overlays. Authored on a 4x4 footprint.
    "enterprise": FlatRideSpec(
        frames=49, directions=4, rider_slots=48, rotation_mode=2, direction_minor=True,
    ),
    # MotionSimulator.cpp: `base + direction + flatRideAnimationFrame * 4`, the same
    # direction-minor 4-direction ring as the enterprise, but the engine cycles it
    # through Status::simulatorOperating (a hardcoded tilt sequence) rather than a
    # `rotationMode`, so no mode is set. 35 poses (frames 0-3 are the restraint
    # load stages, 4-34 the tilt motion); the boarding stairs are base-game
    # graphics, so the object provides only the tilting pod. No rider overlays.
    "motion_simulator": FlatRideSpec(
        frames=35, directions=4, rider_slots=0, direction_minor=True,
    ),
    # SwingingShip.cpp: `base + plane*9 + swing*18` (+ frameNum for riders). The
    # ship is stored as 2 planes (the camera diagonals; directions 0/2 and 1/3
    # share a plane, the engine mirrors the swing sign for the back views) x 19
    # swing blocks (block 0 upright, 1-9 lean one way, 10-18 the other), each ship
    # sprite trailed by 8 interleaved rider sprites (emitted blank). The A-frame
    # supports are base-game graphics, so the object provides only the ship. The
    # 19 poses are authored in swing-block order (upright, then each lean ramp);
    # the add-on samples a keyframed swing into that order.
    "swinging_ship": FlatRideSpec(
        frames=19, directions=2, rider_slots=0, direction_minor=True, blank_sub_slots=8,
    ),
    # SpaceRings.cpp: `base + direction + flatRideAnimationFrame * 4`, the same
    # direction-minor 4-direction ring as the enterprise/simulator, here a single
    # ring's full 88-pose tumble. The object provides one ring (the engine spawns
    # carsPerFlatRide=4 of them); 4*88 rider overlays follow at offset 352
    # (`base + 352 + direction + frame*4`), emitted blank.
    "space_rings": FlatRideSpec(
        frames=88, directions=4, rider_slots=352, direction_minor=True,
    ),
}

# The ride build-menu preview box is 112x112 pixels.
PREVIEW_BOX = 112
