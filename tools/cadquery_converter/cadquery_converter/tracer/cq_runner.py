"""Execute CadQuery source with runtime tracing enabled."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]

from .instrument import get_active_trace, install_instrumentation, remove_instrumentation, reset_trace
from .trace_schema import OperationTrace


def run_cadquery_traced_inprocess(source: str) -> OperationTrace:
    install_instrumentation()
    reset_trace()
    namespace: dict = {}
    cleaned = source.replace("show_object(", "# show_object(")

    try:
        import cadquery as cq

        namespace["cq"] = cq
        exec(compile(cleaned, "<cadquery_traced>", "exec"), namespace, namespace)
        result = namespace.get("result")
        if result is None:
            trace = get_active_trace()
            trace.cq_status = "error"
            trace.error = "CadQuery result missing"
            return trace
        solid = result.val()
        trace = get_active_trace()
        trace.cq_volume = float(solid.Volume())
        bbox = solid.BoundingBox()
        trace.cq_bbox = [
            float(bbox.xmin),
            float(bbox.ymin),
            float(bbox.zmin),
            float(bbox.xmax),
            float(bbox.ymax),
            float(bbox.zmax),
        ]
    except Exception as exc:
        trace = get_active_trace()
        trace.cq_status = "error"
        trace.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"
    finally:
        remove_instrumentation()

    return get_active_trace()


def run_cadquery_traced(
    source: str,
    *,
    timeout: Optional[float] = 120.0,
    use_subprocess: bool = False,
) -> OperationTrace:
    if not use_subprocess:
        return run_cadquery_traced_inprocess(source)

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(_PACKAGE_ROOT)
        if not pythonpath
        else f"{_PACKAGE_ROOT}{os.pathsep}{pythonpath}"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        encoding="utf-8",
        delete=False,
    ) as handle:
        handle.write(source)
        source_path = Path(handle.name)

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "cadquery_converter.tracer._trace_worker",
                str(source_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        trace = OperationTrace(cq_status="failed", error=f"CadQuery trace timed out after {timeout}s")
        if exc.stdout:
            trace.error += f"\npartial stdout: {exc.stdout[:500]}"
        return trace
    except Exception as exc:
        return OperationTrace(
            cq_status="failed",
            error=f"subprocess launch failed: {type(exc).__name__}: {exc}",
        )
    finally:
        source_path.unlink(missing_ok=True)

    if not proc.stdout.strip():
        return OperationTrace(
            cq_status="failed",
            error=proc.stderr.strip() or f"trace worker exited with code {proc.returncode}",
        )

    try:
        payload = json.loads(proc.stdout)
        trace = OperationTrace.from_dict(payload)
    except json.JSONDecodeError as exc:
        return OperationTrace(
            cq_status="failed",
            error=f"invalid trace JSON: {exc}\nstderr: {proc.stderr.strip()}",
        )

    if proc.returncode != 0 and trace.cq_status == "ok":
        trace.cq_status = "failed"
        if proc.stderr.strip():
            trace.error = proc.stderr.strip()
    return trace
