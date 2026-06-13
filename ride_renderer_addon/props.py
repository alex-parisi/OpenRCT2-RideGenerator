"""
Blender PropertyGroups for the ride (stall) add-on.
"""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Material, Object, PropertyGroup, Scene
from openrct2_object_common.blender.props import (
    DEFAULT_DITHER_MODE,
    DITHER_MODE_ITEMS,
    SCALE_PRESET_ITEMS,
    SharedLight,
    scale_preset_update,
    simple_items,
)
from openrct2_ride_generator.constants import COLOR_NAMES, SHOP_ITEMS, STALL_TYPES, StallKind
from openrct2_x7_renderer.constants import TILE_SIZE

STALL_TYPE_ITEMS = [
    ("food_stall", "Food Stall", "Sells food items (4 view sprites)"),
    ("drink_stall", "Drink Stall", "Sells drink items (4 view sprites)"),
    ("shop", "Shop", "Sells souvenirs: balloons, toys, hats, ... (4 view sprites)"),
    ("balloon_stall", "Balloon Stall", "The dedicated balloon stall type (4 view sprites)"),
    ("information_kiosk", "Information Kiosk", "Sells maps and umbrellas (4 view sprites)"),
    ("toilets", "Toilets", "Facility guests walk into (6 view sprites, door faces +X)"),
    ("first_aid", "First Aid Room", "Facility guests walk into (6 view sprites, door faces +X)"),
    ("crooked_house", "Crooked House", "3x3 building ride, model centred on the middle tile"),
    ("haunted_house", "Haunted House", "3x3 building ride (ghost animation left blank)"),
    ("circus", "Circus", "3x3 building ride, model centred on the middle tile"),
]

SELLS_ITEMS = [("NONE", "None", "Sells nothing")] + simple_items(sorted(SHOP_ITEMS))

COLOUR_ITEMS = simple_items(COLOR_NAMES)

OBJECT_ROLE_ITEMS = [
    ("GEOMETRY", "Geometry", "Part of the stall model"),
    (
        "DOOR",
        "Door",
        "Facility doorway (door + frame, facing +X): cut into the separate "
        "door sprite so guests sort into it; still part of the building",
    ),
    ("IGNORE", "Ignore", "Not part of the stall"),
]

MATERIAL_REGION_ITEMS = [
    ("NONE", "None", "Plain shaded colour"),
    ("REMAP1", "Remap 1 (primary colour)", "Recoloured by the ride's main colour"),
    ("REMAP2", "Remap 2 (secondary)", "Recoloured by the first additional colour"),
    ("REMAP3", "Remap 3 (tertiary)", "Recoloured by the second additional colour"),
    ("GREYSCALE", "Greyscale", "Greyscale shading region"),
    ("PEEP", "Peep", "Peep region"),
]


def is_facility(stall_type: str) -> bool:
    return STALL_TYPES[stall_type] is StallKind.FACILITY


def is_building(stall_type: str) -> bool:
    return STALL_TYPES[stall_type] is StallKind.BUILDING


def _scale_preset_update(self, _context):
    scale_preset_update(self, _context)


class VGRMaterialSettings(PropertyGroup):
    region: EnumProperty(
        name="Region",
        description="How OpenRCT2 treats this material's pixels",
        items=MATERIAL_REGION_ITEMS,
        default="NONE",
    )
    is_mask: BoolProperty(name="Mask", default=False)
    no_ao: BoolProperty(name="No Ambient Occlusion", default=False)
    edge: BoolProperty(name="Edge AA", default=False)
    dark_edge: BoolProperty(name="Dark Edge AA", default=False)
    no_bleed: BoolProperty(name="No Bleed", default=False)
    texture: PointerProperty(
        name="Texture",
        description="Optional image; must be saved to disk (its file is read at export)",
        type=bpy.types.Image,
    )
    # Phong shading controls
    use_color_override: BoolProperty(
        name="Override Color",
        description="Use the color below instead of the shader's Base Color",
        default=False,
    )
    diffuse_color: FloatVectorProperty(
        name="Color",
        description="Flat diffuse color (used when Override Color is on)",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.8, 0.8, 0.8),
    )
    specular_intensity: FloatProperty(
        name="Specular Intensity",
        description="Brightness of the specular highlight (scales the specular color)",
        default=0.5,
        min=0.0,
        soft_max=1.0,
    )
    specular_exponent: FloatProperty(
        name="Specular Exponent",
        description=(
            "Phong specular exponent: tightness of the highlight (higher = smaller, sharper)"
        ),
        default=50.0,
        min=1.0,
        soft_max=256.0,
    )
    use_specular_tint: BoolProperty(
        name="Tint Highlight",
        description="Tint the specular highlight with the color below (off = white)",
        default=False,
    )
    specular_tint: FloatVectorProperty(
        name="Specular Tint",
        description="Specular highlight color (used when Tint Highlight is on)",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )


class VGRObjectSettings(PropertyGroup):
    role: EnumProperty(
        name="Role",
        description="Whether this object is part of the stall model",
        items=OBJECT_ROLE_ITEMS,
        default="GEOMETRY",
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


VGRLight = SharedLight


class VGRStallSettings(PropertyGroup):
    scale_preset: EnumProperty(
        name="Scale",
        description="How many OBJ units map to one OpenRCT2 tile",
        items=SCALE_PRESET_ITEMS,
        default="REALISTIC",
        update=_scale_preset_update,
    )
    units_per_tile: FloatProperty(
        name="Units / Tile",
        description="OBJ units per OpenRCT2 tile; drives sprite size and tile anchoring",
        default=TILE_SIZE,
        min=0.01,
        soft_max=16.0,
    )
    dither: EnumProperty(
        name="Dither",
        description=(
            "Palette dithering mode. Bayer and Blue noise stay stable across "
            "animation frames; Floyd-Steinberg has higher fidelity but its pattern "
            "shifts per frame"
        ),
        items=DITHER_MODE_ITEMS,
        default=DEFAULT_DITHER_MODE,
    )
    dither_stability: FloatProperty(
        name="Dither Stability",
        description=(
            "Temporal-stability deadband in palette units. Shading changes smaller "
            "than this quantise identically between frames, reducing dither "
            "'swimming' in animations; 0 disables it"
        ),
        default=0.0,
        min=0.0,
        soft_max=16.0,
    )
    id: StringProperty(
        name="Object ID",
        description="Unique id, e.g. openrct2rg.ride.my_stall (avoid vanilla ids)",
        default="openrct2rg.ride.my_stall",
    )
    name: StringProperty(name="Name", default="My Stall")
    description: StringProperty(
        name="Description", default="A stall", description="Shown in the ride window"
    )
    authors: StringProperty(name="Authors", description="Comma-separated", default="")
    version: StringProperty(name="Version", default="1.0")

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

    # Custom lighting
    lights: CollectionProperty(type=VGRLight)
    light_index: IntProperty(default=0)
    show_lights: BoolProperty(
        name="Custom Lighting",
        description="Override the default lighting rig with a custom one",
        default=False,
    )


# VGRLight (= SharedLight) is registered cooperatively, NOT in _CLASSES: Blender shares
# the bundled openrct2_objectcommon wheel across the OpenRCT2 add-ons, so SharedLight is
# one class object — whichever add-on loads first registers it, the rest must skip it
# (else "already registered as a subclass 'SharedLight'"). Mirrors the shared parent
# panel guard in panels.py.
_CLASSES = (
    VGRMaterialSettings,
    VGRObjectSettings,
    VGRColourPreset,
    VGRStallSettings,
)

_shared_light_owned = False


def _register_shared_light():
    """Register SharedLight unless another OpenRCT2 add-on already did.

    Blender shares the bundled wheel, so ``VGRLight`` is the very class object the
    other add-ons register; ``is_registered`` is the reliable cross-add-on check
    (the class is not exposed as ``bpy.types.SharedLight``).
    """
    global _shared_light_owned
    if not VGRLight.is_registered:
        bpy.utils.register_class(VGRLight)
        _shared_light_owned = True


def _unregister_shared_light():
    """Drop SharedLight only if this add-on was the one that registered it."""
    global _shared_light_owned
    if _shared_light_owned:
        bpy.utils.unregister_class(VGRLight)
        _shared_light_owned = False


def register():
    # SharedLight must exist before VGRStallSettings' CollectionProperty(type=VGRLight).
    _register_shared_light()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    Scene.vgr_stall = PointerProperty(type=VGRStallSettings)
    Object.vgr_object = PointerProperty(type=VGRObjectSettings)
    Material.vgr_material = PointerProperty(type=VGRMaterialSettings)


def unregister():
    del Material.vgr_material
    del Object.vgr_object
    del Scene.vgr_stall
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    _unregister_shared_light()
