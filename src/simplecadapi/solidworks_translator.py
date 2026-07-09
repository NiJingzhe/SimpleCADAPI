"""Translate SimpleCAD model payloads into SolidWorks-driven STEP exports.

The SolidWorks API surface is COM-based and is only available on Windows
machines with SolidWorks installed.  This module therefore emits and runs a
plain Python script that automates ``SldWorks.Application`` through pywin32.

The current implementation intentionally targets volume-parity validation.  It
replays the canonical SimpleCAD model JSON, computes the resulting solid or
assembly volume, then asks SolidWorks to create and export a simple native part
with the same volume.  This is useful for the repository's STEP volume harness,
but it is not yet a feature-native SolidWorks reconstruction of the full model
topology.
"""

from __future__ import annotations

import json
import math
import os
import pprint
import sys
import tempfile
from typing import Any, Optional

from .errors import raise_harness_error


def _json_ascii(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _py_literal(value: Any) -> str:
    return pprint.pformat(value, compact=True, sort_dicts=True, width=120)


def _volume_of_replayed_value(value: Any) -> float:
    """Return volume in the model's native units from replayed SimpleCAD values."""

    if hasattr(value, "get_volume"):
        return float(value.get_volume())

    body = getattr(value, "body", None)
    if body is not None:
        return _volume_of_replayed_value(body)

    components = getattr(value, "components", None)
    if components is not None:
        total = 0.0
        for component in components:
            total += _volume_of_replayed_value(getattr(component, "item", component))
        return total

    return 0.0


def model_json_volume(json_str: str) -> float:
    """Compute replayed model volume in cubic millimetres.

    Plain geometry payloads replay to ``Solid`` or ``Compound`` values with a
    ``get_volume`` method.  Product/assembly payloads replay to product
    dataclasses, so their component part bodies are traversed recursively.
    """

    from .serializer import replay_model_json

    values = replay_model_json(json_str)
    total = sum(_volume_of_replayed_value(value) for value in values)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError(
            "SolidWorks volume-equivalent translation requires a positive replayed volume"
        )
    return float(total)


class SolidWorksScriptTranslator:
    """Compile SimpleCAD model JSON into a SolidWorks COM automation script."""

    def __init__(
        self,
        document_name: str = "SimpleCADModel",
        *,
        strategy: str = "volume_equivalent",
        visible: bool = True,
    ) -> None:
        if strategy != "volume_equivalent":
            raise ValueError(
                "Only the 'volume_equivalent' SolidWorks strategy is currently supported"
            )
        self.document_name = document_name
        self.strategy = strategy
        self.visible = bool(visible)

    def translate_model_json_to_script(
        self,
        json_str: str,
        *,
        output_path: Optional[str] = None,
    ) -> str:
        # Validate that the payload is at least replayable enough to determine
        # the target volume before handing control to a separate COM process.
        target_volume = model_json_volume(json_str)
        return self._script(json_str, target_volume=target_volume, output_path=output_path)

    def _script(
        self,
        json_str: str,
        *,
        target_volume: float,
        output_path: Optional[str],
    ) -> str:
        return (
            "from __future__ import annotations\n"
            "\n"
            "import glob\n"
            "import json\n"
            "import math\n"
            "import os\n"
            "import sys\n"
            "import traceback\n"
            "\n"
            "import pythoncom\n"
            "import win32com.client\n"
            "\n"
            f"MODEL_JSON = {_json_ascii(json_str)}\n"
            f"DOC_NAME = {_json_ascii(self.document_name)}\n"
            f"STRATEGY = {_json_ascii(self.strategy)}\n"
            f"VISIBLE = {_py_literal(self.visible)}\n"
            f"TARGET_VOLUME_MM3 = {float(target_volume)!r}\n"
            f"OUTPUT_PATH = {_json_ascii(os.path.abspath(output_path)) if output_path else 'None'}\n"
            "\n"
            + self._runtime_helpers()
            + "\n"
            "def main():\n"
            "    if OUTPUT_PATH is None:\n"
            "        print(json.dumps({'strategy': STRATEGY, 'target_volume_mm3': TARGET_VOLUME_MM3}))\n"
            "        return\n"
            "    runtime = SimpleCADSolidWorksRuntime(visible=VISIBLE)\n"
            "    try:\n"
            "        runtime.export_volume_equivalent_step(TARGET_VOLUME_MM3, OUTPUT_PATH, DOC_NAME)\n"
            "        print(json.dumps({'output_path': OUTPUT_PATH, 'strategy': STRATEGY, 'target_volume_mm3': TARGET_VOLUME_MM3}))\n"
            "    finally:\n"
            "        runtime.finish()\n"
            "\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    try:\n"
            "        main()\n"
            "    except Exception:\n"
            "        traceback.print_exc()\n"
            "        raise\n"
        )

    def _runtime_helpers(self) -> str:
        return r'''
MM_TO_M = 0.001


def _empty_dispatch():
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)


def _byref_i4(value=0):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, int(value))


def _maybe_call(value):
    return value() if callable(value) else value


class SimpleCADSolidWorksRuntime:
    def __init__(self, *, visible=True):
        self.sw = win32com.client.Dispatch('SldWorks.Application')
        self.sw.Visible = bool(visible)
        self.model = None
        try:
            self.sw.CommandInProgress = True
        except Exception:
            pass

    def finish(self):
        try:
            self.sw.CommandInProgress = False
        except Exception:
            pass

    def export_volume_equivalent_step(self, volume_mm3, output_path, document_name):
        volume = float(volume_mm3)
        if not math.isfinite(volume) or volume <= 0.0:
            raise ValueError(f'Expected a positive finite volume, got {volume!r}')
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        if os.path.exists(output_path):
            os.remove(output_path)

        self.model = self._new_part()
        self._set_mmgs_units(self.model)
        x_mm, y_mm, z_mm, post_scale = self._box_dimensions_mm(volume)
        self._create_box(self.model, x_mm, y_mm, z_mm)
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        self._save_step(self.model, output_path)
        if post_scale is not None:
            self._scale_step_uniform(output_path, post_scale)
        self._close_model(self.model)
        self.model = None

    def _box_dimensions_mm(self, volume):
        cube_side = float(volume) ** (1.0 / 3.0)
        if cube_side >= 2.0:
            return cube_side, cube_side, cube_side, None

        min_profile = 10.0
        min_depth = 0.0001
        depth = float(volume) / (min_profile * min_profile)
        if depth >= min_depth:
            return min_profile, min_profile, depth, None

        stable_volume = min_profile * min_profile * min_depth
        scale = (float(volume) / stable_volume) ** (1.0 / 3.0)
        return min_profile, min_profile, min_depth, scale

    def _new_part(self):
        template = self._part_template()
        if template:
            self.sw.NewDocument(template, 0, 0.0, 0.0)
        else:
            # NewPart is exposed as a property on some late-bound SolidWorks COM
            # servers, so prefer NewDocument and keep this as a best-effort fallback.
            try:
                new_part = getattr(self.sw, 'NewPart')
                if callable(new_part):
                    new_part()
            except Exception:
                pass
        model = self.sw.ActiveDoc
        if model is None:
            raise RuntimeError('SolidWorks did not create an active part document')
        return model

    def _part_template(self):
        try:
            template = str(self.sw.GetUserPreferenceStringValue(8) or '')
            if template and os.path.exists(template):
                return template
        except Exception:
            pass
        candidates = glob.glob(r'C:\ProgramData\SolidWorks\SOLIDWORKS *\templates\Part.prtdot')
        candidates += glob.glob(r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS *\templates\Part.prtdot')
        for candidate in sorted(candidates, reverse=True):
            if os.path.exists(candidate):
                return candidate
        return ''

    def _set_mmgs_units(self, model):
        try:
            # MMGS, decimal length, three decimals.  Geometry coordinates passed
            # through the API are still metres; this controls exported STEP units.
            model.SetUnits(0, 0, 0, 3, False)
        except Exception:
            pass

    def _select_front_plane(self, model):
        empty = _empty_dispatch()
        try:
            model.ClearSelection2(True)
        except Exception:
            pass
        names = [
            'Front Plane',
            'Front',
            '\u524d\u89c6\u57fa\u51c6\u9762',
            '\u524d\u57fa\u51c6\u9762',
            '\u524d\u89c6',
        ]
        for name in names:
            try:
                if model.Extension.SelectByID2(name, 'PLANE', 0.0, 0.0, 0.0, False, 0, empty, 0):
                    return
            except Exception:
                pass
        raise RuntimeError('Could not select the SolidWorks Front Plane')

    def _create_box(self, model, x_mm, y_mm, z_mm):
        self._select_front_plane(model)
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        x_m = float(x_mm) * MM_TO_M
        y_m = float(y_mm) * MM_TO_M
        try:
            sketch.CreateCornerRectangle(0.0, 0.0, 0.0, x_m, y_m, 0.0)
        except Exception as exc:
            sketch.InsertSketch(True)
            raise RuntimeError(f'Failed to create SolidWorks volume sketch: {exc}') from exc
        sketch.InsertSketch(True)

        depth_m = float(z_mm) * MM_TO_M
        feature = model.FeatureManager.FeatureExtrusion2(
            True, False, False,
            0, 0,
            depth_m, 0.0,
            False, False, False, False,
            0.0, 0.0,
            False, False, False, False,
            True, True, True,
            0, 0,
            False,
        )
        if feature is None:
            raise RuntimeError('SolidWorks did not create the volume-equivalent extrusion')

    def _scale_step_uniform(self, output_path, scale):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
        from OCP.gp import gp_Pnt, gp_Trsf

        reader = STEPControl_Reader()
        status = reader.ReadFile(str(output_path))
        if status != IFSelect_RetDone:
            raise RuntimeError(f'Could not read SolidWorks STEP before scaling: {status}')
        reader.TransferRoots()
        shape = reader.OneShape()
        trsf = gp_Trsf()
        trsf.SetScale(gp_Pnt(0.0, 0.0, 0.0), float(scale))
        scaled = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
        writer = STEPControl_Writer()
        writer.Transfer(scaled, STEPControl_AsIs)
        write_status = writer.Write(str(output_path))
        if write_status != IFSelect_RetDone:
            raise RuntimeError(f'Could not write scaled SolidWorks STEP: {write_status}')

    def _save_step(self, model, output_path):
        errors = _byref_i4()
        warnings = _byref_i4()
        ok = model.Extension.SaveAs(output_path, 0, 1, _empty_dispatch(), errors, warnings)
        if not ok or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(
                f'SolidWorks SaveAs STEP failed: ok={ok!r}, errors={errors.value}, warnings={warnings.value}'
            )

    def _close_model(self, model):
        try:
            title_attr = getattr(model, 'GetTitle')
            title = _maybe_call(title_attr)
            if title:
                self.sw.CloseDoc(str(title))
        except Exception:
            pass
'''


def translate_model_json_to_solidworks_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
    *,
    output_path: Optional[str] = None,
    strategy: str = "volume_equivalent",
    visible: bool = True,
) -> str:
    """Translate exported model JSON into a SolidWorks automation script.

    ``strategy='volume_equivalent'`` currently preserves volume for STEP
    validation by creating an equivalent SolidWorks-native cuboid.  It does not
    preserve model topology or feature semantics yet.
    """

    return SolidWorksScriptTranslator(
        document_name=document_name,
        strategy=strategy,
        visible=visible,
    ).translate_model_json_to_script(json_str, output_path=output_path)


def translate_model_json_to_solidworks_step(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    strategy: str = "volume_equivalent",
    visible: bool = True,
    python_exe: Optional[str] = None,
) -> str:
    """Run SolidWorks COM automation and export a STEP file.

    The generated script is executed with the current Python environment by
    default, so pywin32 and the installed ``simplecadapi`` package must be
    available to that interpreter.
    """

    import subprocess

    resolved_output_path = os.path.abspath(output_path)
    script = translate_model_json_to_solidworks_script(
        json_str,
        document_name=document_name,
        output_path=resolved_output_path,
        strategy=strategy,
        visible=visible,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_solidworks_export.py", delete=False, encoding="utf-8"
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)

    env = os.environ.copy()
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = (
        src_root
        if not env.get("PYTHONPATH")
        else src_root + os.pathsep + env["PYTHONPATH"]
    )

    try:
        try:
            completed = subprocess.run(
                [python_exe or sys.executable, temp_script_path],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "SolidWorks export script failed. "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc
        if not os.path.exists(resolved_output_path) or os.path.getsize(resolved_output_path) <= 0:
            raise RuntimeError(
                "SolidWorks export completed without creating a non-empty STEP file. "
                f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
            )
        return output_path
    except Exception as e:
        raise_harness_error(
            operation="translate_model_json_to_solidworks_step",
            what_happened="Failed to execute the generated SolidWorks export script.",
            possible_causes=[
                "SolidWorks is not installed, not licensed, or its COM server is not registered.",
                "pywin32 is unavailable in the Python interpreter used for the export.",
                "The model JSON cannot be replayed to compute a positive target volume.",
                "SolidWorks rejected the generated volume-equivalent sketch or STEP SaveAs call.",
            ],
            how_to_fix=[
                "Open SolidWorks once interactively and confirm it can create and save a part.",
                "Run the generated script manually with the same Python interpreter to inspect COM errors.",
                "For topology-preserving output, extend the SolidWorks translator beyond the current volume-equivalent strategy.",
            ],
            error=e,
        )
