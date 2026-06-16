"""
Blender operators for the ride (stall) add-on: test render, threaded export,
and colour-preset/light list management.
"""

import os

from bpy.props import StringProperty
from openrct2_object_common.blender.collection_ops import make_collection_ops
from openrct2_object_common.blender.lights_ui import make_light_ops
from openrct2_object_common.blender.modal import (
    ExportParkobjModalBase,
    RenderModalBase,
    TestRenderModalBase,
)
from openrct2_object_common.blender.registration import register_classes, unregister_classes
from openrct2_object_common.config import LoadError
from openrct2_object_common.parkobj import parkobj_filename
from openrct2_ride_generator.exporter import export_stall_test, export_stall_to

from . import scene_to_stall


class _StallModalBase(RenderModalBase):
    """Shared base for the stall render operators."""

    _clean_error_types = (scene_to_stall.SceneError, LoadError)
    _invalid_prefix = "Invalid stall"

    def _build(self, context):
        return scene_to_stall.build_stall_from_scene(context)

    def _prepare(self, context, payload) -> None:
        self._read_render_settings(context.scene.vgr_stall)


class VGR_OT_test_render(TestRenderModalBase, _StallModalBase):
    bl_idname = "vgr.test_render"
    bl_label = "Test Render"
    bl_description = "Render the stall quickly and show it in the Image Editor"

    _tmp_prefix = "vgr_test_"

    def _render(self, payload) -> None:
        # Render at the real in-game scale
        ctx = self._make_context(payload.units_per_tile)
        export_stall_test(payload, ctx, self._tmp)
        self._png = os.path.join(self._tmp, "preview_combined.png")


class VGR_OT_export_parkobj(ExportParkobjModalBase, _StallModalBase):
    bl_idname = "vgr.export_parkobj"
    bl_label = "Export .parkobj"
    bl_description = "Render every sprite and write an OpenRCT2 ride .parkobj"

    _tmp_prefix = "vgr_export_"

    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ".parkobj"
    filter_glob: StringProperty(default="*.parkobj", options={"HIDDEN"})

    def _default_filename(self, context) -> str:
        return parkobj_filename(context.scene.vgr_stall.id, default="stall")

    def _render(self, payload) -> None:
        ctx = self._make_context(payload.units_per_tile)
        export_stall_to(payload, ctx, self._parkobj, self._work, progress=self.set_progress)


VGR_OT_preset_add, VGR_OT_preset_remove = make_collection_ops(
    prefix="vgr",
    name="preset",
    settings_attr="vgr_stall",
    coll_attr="colour_presets",
    index_attr="preset_index",
    add_label="Add Colour Preset",
    add_description="Add a carColours preset",
    remove_label="Remove Colour Preset",
    remove_description="Remove the selected colour preset",
)

VGR_OT_light_add, VGR_OT_light_remove = make_light_ops(prefix="vgr", settings_attr="vgr_stall")


_CLASSES = (
    VGR_OT_test_render,
    VGR_OT_export_parkobj,
    VGR_OT_preset_add,
    VGR_OT_preset_remove,
    VGR_OT_light_add,
    VGR_OT_light_remove,
)


def register():
    register_classes(_CLASSES)


def unregister():
    unregister_classes(_CLASSES)
