"""
UI panels for the ride (stall) add-on: scene settings (3D View N-panel) +
per-object role + per-material region."""

import bpy
from bpy.types import Panel, UIList

from .props import is_building, is_facility


class VGR_UL_presets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text="", icon="COLOR")
        row.prop(item, "main", text="")
        row.prop(item, "additional_1", text="")
        row.prop(item, "additional_2", text="")


class VGR_UL_lights(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text="", icon="LIGHT")
        row.prop(item, "type", text="")
        row.prop(item, "strength", text="")


class VGR_PT_stall(Panel):
    bl_label = "OpenRCT2 Ride"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenRCT2"

    def draw(self, context):
        layout = self.layout
        ss = context.scene.vgr_stall

        layout.prop(ss, "scale_preset")
        if ss.scale_preset == "CUSTOM":
            layout.prop(ss, "units_per_tile")
        layout.prop(ss, "dither")

        box = layout.box()
        box.label(text="Identity", icon="INFO")
        box.prop(ss, "id")
        box.prop(ss, "name")
        box.prop(ss, "description")
        box.prop(ss, "authors")
        box.prop(ss, "version")

        box = layout.box()
        box.label(text="Stall", icon="HOME")
        box.prop(ss, "stall_type")
        if is_facility(ss.stall_type):
            box.prop(ss, "facility_door_split")
            box.label(text="Door faces +X; give the doorway object the Door role.", icon="INFO")
        elif is_building(ss.stall_type):
            box.prop(ss, "seats")
            box.label(text="3x3 footprint, centred on the origin tile.", icon="INFO")
        else:
            row = box.row(align=True)
            row.prop(ss, "sells_1", text="Sells")
            row.prop(ss, "sells_2", text="")
        box.prop(ss, "clearance")

        cbox = layout.box()
        cbox.label(text="Colours", icon="COLOR")
        cbox.prop(ss, "disable_painting")
        if not ss.disable_painting:
            cbox.label(text="Presets recolour Remap materials:")
            row = cbox.row()
            row.template_list(
                "VGR_UL_presets", "", ss, "colour_presets", ss, "preset_index", rows=3
            )
            col = row.column(align=True)
            col.operator("vgr.preset_add", icon="ADD", text="")
            col.operator("vgr.preset_remove", icon="REMOVE", text="")
            if not ss.colour_presets:
                cbox.label(text="No presets - black is used.", icon="INFO")

        _draw_lights(layout, ss)

        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("vgr.test_render", icon="RENDER_STILL")
        col.operator("vgr.export_parkobj", icon="EXPORT")


def _draw_lights(layout, ss):
    box = layout.box()
    row = box.row()
    row.prop(
        ss, "show_lights",
        icon="TRIA_DOWN" if ss.show_lights else "TRIA_RIGHT", emboss=False,
    )
    row.label(text="", icon="LIGHT_SUN")
    if ss.show_lights:
        row = box.row()
        row.template_list("VGR_UL_lights", "", ss, "lights", ss, "light_index", rows=3)
        col = row.column(align=True)
        col.operator("vgr.light_add", icon="ADD", text="")
        col.operator("vgr.light_remove", icon="REMOVE", text="")
        if ss.lights:
            light = ss.lights[ss.light_index]
            sub = box.column()
            sub.prop(light, "type")
            sub.prop(light, "shadow")
            sub.prop(light, "direction")
            sub.prop(light, "strength")
        else:
            box.label(text="No lights - using the default rig.", icon="INFO")


def _draw_material_settings(layout, ms):
    """Draw a material's OpenRCT2 region/flags/shading settings."""
    layout.prop(ms, "region")
    col = layout.column(align=True)
    col.prop(ms, "is_mask")
    col.prop(ms, "no_ao")
    col.prop(ms, "edge")
    col.prop(ms, "dark_edge")
    col.prop(ms, "no_bleed")
    layout.prop(ms, "texture")

    col = layout.column(align=True)
    col.label(text="Shading")
    row = col.row(align=True)
    row.prop(ms, "use_color_override", text="")
    sub = row.row()
    sub.enabled = ms.use_color_override
    sub.prop(ms, "diffuse_color", text="Color")
    col.prop(ms, "specular_exponent")
    col.prop(ms, "specular_intensity")
    row = col.row(align=True)
    row.prop(ms, "use_specular_tint", text="")
    sub = row.row()
    sub.enabled = ms.use_specular_tint
    sub.prop(ms, "specular_tint", text="Specular Tint")


def _draw_object_settings(layout, obj):
    """Draw the active object's role and its materials, folded together so a
    stall part is authored from the viewport sidebar without leaving it."""
    layout.prop(obj.vgr_object, "role")
    if obj.vgr_object.role == "IGNORE":
        return

    layout.prop(obj.vgr_object, "is_ghost")

    box = layout.box()
    box.label(text="Materials", icon="MATERIAL")
    if not obj.material_slots:
        box.label(text="No materials on this object.", icon="INFO")
        return
    if len(obj.material_slots) > 1:
        box.template_list(
            "MATERIAL_UL_matslots", "", obj, "material_slots",
            obj, "active_material_index", rows=2,
        )
    mat = obj.active_material
    if mat is None:
        box.label(text="Empty material slot.", icon="INFO")
    else:
        _draw_material_settings(box, mat.vgr_material)


# Shared "Selected Object" container (shared across the OpenRCT2 add-ons)
_SHARED_PARENT_IDNAME = "OPENRCT2_PT_selected_object"


class OPENRCT2_PT_selected_object(Panel):
    bl_idname = _SHARED_PARENT_IDNAME
    bl_label = "Selected Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenRCT2"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        pass


def _register_shared_parent():
    """Register the shared parent unless another add-on already did."""
    if not hasattr(bpy.types, _SHARED_PARENT_IDNAME):
        bpy.utils.register_class(OPENRCT2_PT_selected_object)


def _unregister_shared_parent():
    """Drop the shared parent only once no add-on's child still nests under it."""
    cls = getattr(bpy.types, _SHARED_PARENT_IDNAME, None)
    if cls is None:
        return
    for name in dir(bpy.types):
        if getattr(getattr(bpy.types, name, None), "bl_parent_id", "") == _SHARED_PARENT_IDNAME:
            return
    bpy.utils.unregister_class(cls)


class VGR_PT_object_view3d(Panel):
    """The active object's stall settings, as a child of "Selected Object"."""

    bl_label = "Ride"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenRCT2"
    bl_parent_id = _SHARED_PARENT_IDNAME
    bl_order = 2

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and hasattr(obj, "vgr_object")

    def draw(self, context):
        _draw_object_settings(self.layout, context.object)


_CLASSES = (
    VGR_UL_presets,
    VGR_UL_lights,
    VGR_PT_stall,
    VGR_PT_object_view3d,
)


def register():
    _register_shared_parent()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    _unregister_shared_parent()
