"""
UI panels for the ride (stall) add-on: scene settings (3D View N-panel) +
per-object role + per-material region."""

from bpy.types import Panel, UIList
from openrct2_object_common.blender.lights_ui import draw_lights_rig, make_lights_uilist
from openrct2_object_common.blender.object_panel import (
    draw_dither_box,
    draw_identity_box,
    draw_materials_box,
    draw_render_buttons,
    draw_scale,
    make_object_view3d_panel,
    register_shared_parent,
    unregister_shared_parent,
)
from openrct2_object_common.blender.registration import register_classes, unregister_classes

from .props import can_sell, is_building, is_facility, is_flat_ride


class VGR_UL_presets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text="", icon="COLOR")
        row.prop(item, "main", text="")
        row.prop(item, "additional_1", text="")
        row.prop(item, "additional_2", text="")


VGR_UL_lights = make_lights_uilist("VGR_UL_lights")


class VGR_PT_stall(Panel):
    bl_label = "OpenRCT2 Ride"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenRCT2"

    def draw(self, context):
        layout = self.layout
        ss = context.scene.vgr_stall

        draw_scale(layout, ss)
        draw_identity_box(layout, ss, ("id", "name", "description", "authors", "version"))
        draw_dither_box(layout, ss)

        box = layout.box()
        box.label(text="Stall", icon="HOME")
        box.prop(ss, "stall_type")
        if is_facility(ss.stall_type):
            box.prop(ss, "facility_door_split")
            box.label(text="Door faces +X; give the doorway object the Door role.", icon="INFO")
        elif is_flat_ride(ss.stall_type):
            box.prop(ss, "seats")
            box.label(text="3x3 footprint, centred on the origin tile.", icon="INFO")
            box.label(text="Keyframe a 360-degree spin over the scene frame range.", icon="INFO")
        elif is_building(ss.stall_type):
            box.prop(ss, "seats")
            box.label(text="3x3 footprint, centred on the origin tile.", icon="INFO")
        elif can_sell(ss.stall_type):
            row = box.row(align=True)
            row.prop(ss, "sells_1", text="Sells")
            row.prop(ss, "sells_2", text="")
        else:
            box.label(text="Dispenses cash; sells nothing.", icon="INFO")
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

        draw_lights_rig(layout, ss, prefix="vgr", uilist_name="VGR_UL_lights")

        draw_render_buttons(layout, "vgr.test_render", "vgr.export_parkobj")


def _draw_object_settings(layout, obj):
    """Draw the active object's role and its materials, folded together so a
    stall part is authored from the viewport sidebar without leaving it."""
    layout.prop(obj.vgr_object, "role")
    if obj.vgr_object.role == "IGNORE":
        return

    layout.prop(obj.vgr_object, "is_ghost")

    draw_materials_box(layout, obj, "vgr_material")


VGR_PT_object_view3d = make_object_view3d_panel(
    name="VGR_PT_object_view3d",
    label="Ride",
    order=2,
    prop_attr="vgr_object",
    draw=lambda layout, context: _draw_object_settings(layout, context.object),
)


_CLASSES = (
    VGR_UL_presets,
    VGR_UL_lights,
    VGR_PT_stall,
    VGR_PT_object_view3d,
)


def register():
    register_shared_parent()
    register_classes(_CLASSES)


def unregister():
    unregister_classes(_CLASSES)
    unregister_shared_parent()
