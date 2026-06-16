"""
Blender PropertyGroups for the ride (stall) add-on.
"""

from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Material, Object, PropertyGroup, Scene
from openrct2_object_common.blender.props import (
    MATERIAL_REGION_ITEMS,
    SharedMaterialSettings,
    SharedRenderSettings,
    register_settings,
    simple_items,
    unregister_settings,
)
from openrct2_ride_generator.constants import (
    COLOR_NAMES,
    FLAT_RIDE_SPECS,
    SHOP_ITEMS,
    SHOP_SELL_TYPES,
    STALL_TYPES,
    StallKind,
)

STALL_TYPE_ITEMS = [
    ("food_stall", "Food Stall", "Sells food items (4 view sprites)"),
    ("drink_stall", "Drink Stall", "Sells drink items (4 view sprites)"),
    ("shop", "Shop", "Sells souvenirs: balloons, toys, hats, ... (4 view sprites)"),
    ("balloon_stall", "Balloon Stall", "The dedicated balloon stall type (4 view sprites)"),
    ("information_kiosk", "Information Kiosk", "Sells maps and umbrellas (4 view sprites)"),
    ("cash_machine", "Cash Machine", "ATM that dispenses cash and sells nothing (4 view sprites)"),
    ("toilets", "Toilets", "Facility guests walk into (6 view sprites, door faces +X)"),
    ("first_aid", "First Aid Room", "Facility guests walk into (6 view sprites, door faces +X)"),
    ("crooked_house", "Crooked House", "3x3 building ride, model centred on the middle tile"),
    ("haunted_house", "Haunted House", "3x3 building ride (ghost animation left blank)"),
    ("circus", "Circus", "3x3 building ride, model centred on the middle tile"),
    ("3d_cinema", "3D Cinema", "3x3 building ride (thrill), model centred on the middle tile"),
    ("merry_go_round", "Merry-Go-Round",
     "Animated 3x3 flat ride: keyframe a 360-degree spin; the add-on samples it "
     "(give riders the Rider role for visible riders)"),
    ("ferris_wheel", "Ferris Wheel",
     "Animated 1x4 flat ride: keyframe the wheel spin (gondolas stay upright); "
     "give riders the Rider role for visible riders"),
    ("twist", "Twist",
     "Animated 3x3 flat ride: keyframe a 360-degree spin (symmetric, like the carousel)"),
    ("enterprise", "Enterprise",
     "Animated 4x4 flat ride: keyframe the tilted wheel spin (4 directions)"),
    ("motion_simulator", "Motion Simulator",
     "Animated 2x2 flat ride: keyframe the pod's pitch/roll (4 directions, 35 poses)"),
    ("swinging_ship", "Swinging Ship",
     "Animated 1x5 flat ride: keyframe a back-and-forth swing; the add-on samples it"),
    ("space_rings", "Space Rings",
     "Animated 3x3 flat ride: keyframe one ring's 360-degree tumble (the engine spawns four)"),
]

SELLS_ITEMS = [("NONE", "None", "Sells nothing")] + simple_items(sorted(SHOP_ITEMS))

COLOUR_ITEMS = simple_items(COLOR_NAMES)

def is_facility(stall_type: str) -> bool:
    return stall_type in STALL_TYPES and STALL_TYPES[stall_type] is StallKind.FACILITY


def is_building(stall_type: str) -> bool:
    return stall_type in STALL_TYPES and STALL_TYPES[stall_type] is StallKind.BUILDING


def is_flat_ride(stall_type: str) -> bool:
    return stall_type in STALL_TYPES and STALL_TYPES[stall_type] is StallKind.FLAT_RIDE


def supports_riders(stall_type: str) -> bool:
    """Flat rides whose engine rider layout is known, so a Rider-role mesh can be
    sampled into the rider ring (or, for the swinging ship, its bench sub-slots)."""
    spec = FLAT_RIDE_SPECS.get(stall_type)
    return spec is not None and spec.supports_riders


def can_sell(stall_type: str) -> bool:
    """Shop-kind types that may carry a `sells` item (the cash machine cannot)."""
    return stall_type in SHOP_SELL_TYPES


# Object roles, keyed by identifier -> (label, description, stable id). The id is
# fixed so the *context-filtered* items list (Door only for facilities, Rider only
# for rider-bearing flat rides) never reindexes a stored value -- a callback-driven
# EnumProperty is stored by its number, not its identifier.
_ROLE_DEFS = {
    "GEOMETRY": ("Geometry", "Part of the ride model", 0),
    "DOOR": (
        "Door",
        "Facility doorway (door + frame, facing +X): cut into the separate door "
        "sprite so guests sort into it; still part of the building "
        "(facility ride types only)",
        1,
    ),
    "IGNORE": ("Ignore", "Not part of the ride", 2),
    "RIDER": (
        "Rider",
        "A seated rider-pair the engine draws over the structure, recoloured per "
        "rider by the peep's t-shirt colour (give the two riders Remap 1 / Remap 2 "
        "materials); sampled into the ride's rider ring as it spins "
        "(merry-go-round and ferris wheel only)",
        3,
    ),
}


def _role_item(identifier: str) -> tuple[str, str, str, int, int]:
    label, desc, num = _ROLE_DEFS[identifier]
    return (identifier, label, desc, 0, num)


# Blender garbage-collects an items callback's return value unless a reference is
# held, so cache each filtered list by its (door, rider) signature.
_ROLE_ITEMS_CACHE: dict[tuple[bool, bool], list[tuple[str, str, str, int, int]]] = {}


def object_role_items(self, context):
    """Role choices for the active ride type: Geometry / Ignore always, Door only
    for facilities, Rider only for the rider-bearing flat rides."""
    stall_type = ""
    if context is not None and context.scene is not None:
        stall_type = context.scene.vgr_stall.stall_type
    key = (is_facility(stall_type), supports_riders(stall_type))
    cached = _ROLE_ITEMS_CACHE.get(key)
    if cached is None:
        items = [_role_item("GEOMETRY")]
        if key[0]:
            items.append(_role_item("DOOR"))
        if key[1]:
            items.append(_role_item("RIDER"))
        items.append(_role_item("IGNORE"))
        _ROLE_ITEMS_CACHE[key] = items
        cached = items
    return cached


class VGRMaterialSettings(SharedMaterialSettings):
    # Shared renderer/baking/Phong fields come from SharedMaterialSettings; only
    # the region enum (its regions + default) is stall-specific.
    region: EnumProperty(
        name="Region",
        description="How OpenRCT2 treats this material's pixels",
        items=MATERIAL_REGION_ITEMS,
        default="NONE",
    )


class VGRObjectSettings(PropertyGroup):
    role: EnumProperty(
        name="Role",
        description="Whether this object is part of the ride model",
        items=object_role_items,
    )
    is_ghost: BoolProperty(
        name="Ghost",
        description=(
            "Render this object as ghost geometry: primary rays pass through it "
            "(so it is not drawn) while it still contributes to the silhouette "
            "and ambient occlusion of solid parts"
        ),
        default=False,
    )


class VGRColourPreset(PropertyGroup):
    """One carColours preset: main + two additional remap colours."""

    main: EnumProperty(name="Main", items=COLOUR_ITEMS, default="black")
    additional_1: EnumProperty(name="Additional 1", items=COLOUR_ITEMS, default="black")
    additional_2: EnumProperty(name="Additional 2", items=COLOUR_ITEMS, default="black")


class VGRStallSettings(SharedRenderSettings):
    # scale_preset / units_per_tile / dither / dither_stability / authors /
    # version / lights come from SharedRenderSettings; only the per-object
    # identity and the stall-specific fields live here.
    id: StringProperty(
        name="Object ID",
        description="Unique id, e.g. openrct2rg.ride.my_stall (avoid vanilla ids)",
        default="openrct2rg.ride.my_stall",
    )
    name: StringProperty(name="Name", default="My Stall")
    description: StringProperty(
        name="Description", default="A stall", description="Shown in the ride window"
    )

    stall_type: EnumProperty(
        name="Ride Type",
        description="Which stall/facility ride type the object registers as",
        items=STALL_TYPE_ITEMS,
        default="food_stall",
    )
    sells_1: EnumProperty(
        name="Sells",
        description="First shop item sold (facilities sell nothing)",
        items=SELLS_ITEMS,
        default="NONE",
    )
    sells_2: EnumProperty(
        name="Sells (2nd)",
        description="Optional second shop item (e.g. the kiosk's map + umbrella)",
        items=SELLS_ITEMS,
        default="NONE",
    )
    clearance: IntProperty(
        name="Clearance",
        description="Overhead clearance in world-Z units (8 per height step); 0 = per-type default",
        default=0,
        min=0,
        max=255,
    )
    seats: IntProperty(
        name="Capacity",
        description="Guests per session for building rides; 0 = per-type default",
        default=0,
        min=0,
        max=255,
    )
    disable_painting: BoolProperty(
        name="Disable Painting",
        description="Hide the colour tab (off pairs with Remap materials + colour presets)",
        default=True,
    )
    facility_door_split: BoolProperty(
        name="Split Doorway",
        description=(
            "Cut the doorway (objects with the Door role) into its own sprite "
            "so guests sort into it (facilities only); off renders the full "
            "building everywhere"
        ),
        default=True,
    )

    colour_presets: CollectionProperty(type=VGRColourPreset)
    preset_index: IntProperty(default=0)


# SharedLight (the lights rig's item type, carried by SharedRenderSettings) is
# registered cooperatively (see register_shared_light), NOT in _CLASSES: the
# bundled wheel is shared across the OpenRCT2 add-ons, so only the first one to
# load may register the single SharedLight class object.
_CLASSES = (
    VGRMaterialSettings,
    VGRObjectSettings,
    VGRColourPreset,
    VGRStallSettings,
)

_POINTERS = (
    (Scene, "vgr_stall", VGRStallSettings),
    (Object, "vgr_object", VGRObjectSettings),
    (Material, "vgr_material", VGRMaterialSettings),
)


def register():
    register_settings(_CLASSES, _POINTERS)


def unregister():
    unregister_settings(_CLASSES, _POINTERS)
