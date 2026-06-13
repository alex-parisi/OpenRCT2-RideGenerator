"""
Blender operators for the ride (stall) add-on: test render, threaded export,
and colour-preset/light list management.
"""

import os
import shutil
import tempfile
import time

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from openrct2_object_common.blender.lights import lights_from_items
from openrct2_object_common.blender.modal import RenderModalBase
from openrct2_object_common.cli import make_context
from openrct2_object_common.config import LoadError
from openrct2_ride_generator.exporter import export_stall_test, export_stall_to

from . import scene_to_stall


def _parkobj_filename(object_id: str) -> str:
    return (object_id or "stall").replace("/", "_") + ".parkobj"


class _StallModalBase(RenderModalBase):
    """Shared base for the stall render operators."""

    _clean_error_types = (scene_to_stall.SceneError, LoadError)
    _invalid_prefix = "Invalid stall"

    def _build(self, context):
        return scene_to_stall.build_stall_from_scene(context)

    def _prepare(self, context, payload) -> None:
        self._lights = lights_from_items(context.scene.vgr_stall.lights)
        self._dither = context.scene.vgr_stall.dither


# The previous test render's output directory. Its PNG must outlive the
# operator (the Image Editor reads it from disk), so it is only removed when
# the next test render replaces it.
_last_test_dir: str | None = None


class VGR_OT_test_render(_StallModalBase):
    bl_idname = "vgr.test_render"
    bl_label = "Test Render"
    bl_description = "Render the stall quickly and show it in the Image Editor"

    _status_verb = "Rendering test"

    def _prepare(self, context, payload) -> None:
        global _last_test_dir
        super()._prepare(context, payload)
        if _last_test_dir is not None:
            shutil.rmtree(_last_test_dir, ignore_errors=True)
        self._tmp = tempfile.mkdtemp(prefix="vgr_test_")
        _last_test_dir = self._tmp
        self._png = None

    def _render(self, payload) -> None:
        # Render at the real in-game scale
        ctx = make_context(self._lights, payload.units_per_tile, False, dither=self._dither)
        export_stall_test(payload, ctx, self._tmp)
        self._png = os.path.join(self._tmp, "preview_combined.png")

    def _on_success(self, context):
        if not self._png or not os.path.exists(self._png):
            self.report({"WARNING"}, "Render produced no sprite")
            return {"CANCELLED"}
        img = bpy.data.images.load(self._png, check_existing=False)
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = img
                break
        self.report({"INFO"}, f"Test sprite loaded: {img.name}")
        return {"FINISHED"}


class VGR_OT_export_parkobj(_StallModalBase):
    bl_idname = "vgr.export_parkobj"
    bl_label = "Export .parkobj"
    bl_description = "Render every sprite and write an OpenRCT2 ride .parkobj"

    _status_verb = "Exporting .parkobj"

    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ".parkobj"
    filter_glob: StringProperty(default="*.parkobj", options={"HIDDEN"})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = _parkobj_filename(context.scene.vgr_stall.id)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def _prepare(self, context, payload) -> None:
        super()._prepare(context, payload)
        self._parkobj = bpy.path.abspath(self.filepath)
        self._work = tempfile.mkdtemp(prefix="vgr_export_")

    def _render(self, payload) -> None:
        ctx = make_context(self._lights, payload.units_per_tile, False, dither=self._dither)
        try:
            export_stall_to(payload, ctx, self._parkobj, self._work, progress=self.set_progress)
        finally:
            shutil.rmtree(self._work, ignore_errors=True)

    def _on_success(self, context):
        elapsed = int(time.monotonic() - self._start_time)
        build = f" (build {self._build_secs}s)" if self._build_secs else ""
        name = os.path.basename(self._parkobj)
        self.report({"INFO"}, f"Exported {name} in {elapsed}s{build}")
        return {"FINISHED"}


class VGR_OT_preset_add(Operator):
    bl_idname = "vgr.preset_add"
    bl_label = "Add Colour Preset"
    bl_description = "Add a carColours preset"

    def execute(self, context):
        ss = context.scene.vgr_stall
        ss.colour_presets.add()
        ss.preset_index = len(ss.colour_presets) - 1
        return {"FINISHED"}


class VGR_OT_preset_remove(Operator):
    bl_idname = "vgr.preset_remove"
    bl_label = "Remove Colour Preset"
    bl_description = "Remove the selected colour preset"

    def execute(self, context):
        ss = context.scene.vgr_stall
        if not ss.colour_presets:
            return {"CANCELLED"}
        ss.colour_presets.remove(ss.preset_index)
        ss.preset_index = max(0, min(ss.preset_index, len(ss.colour_presets) - 1))
        return {"FINISHED"}


class VGR_OT_light_add(Operator):
    bl_idname = "vgr.light_add"
    bl_label = "Add Light"
    bl_description = "Add a light to the custom lighting rig"

    def execute(self, context):
        ss = context.scene.vgr_stall
        ss.lights.add()
        ss.light_index = len(ss.lights) - 1
        return {"FINISHED"}


class VGR_OT_light_remove(Operator):
    bl_idname = "vgr.light_remove"
    bl_label = "Remove Light"
    bl_description = "Remove the selected light"

    def execute(self, context):
        ss = context.scene.vgr_stall
        if not ss.lights:
            return {"CANCELLED"}
        ss.lights.remove(ss.light_index)
        ss.light_index = max(0, min(ss.light_index, len(ss.lights) - 1))
        return {"FINISHED"}


_CLASSES = (
    VGR_OT_test_render,
    VGR_OT_export_parkobj,
    VGR_OT_preset_add,
    VGR_OT_preset_remove,
    VGR_OT_light_add,
    VGR_OT_light_remove,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
