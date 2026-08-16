"""Trusted-side comparison bundle and result classification for benchmarks."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
import hashlib
import hmac
import math
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence


_CREATE_SUSPENDED = 0x00000004
_EVIDENCE_KEY = secrets.token_bytes(32)


class _TrustedEvidence(dict[str, Any]):
    """Process-local seal over an evaluator-owned JSON-compatible mapping."""

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        evidence_kind: str,
        context: Mapping[str, Any],
    ) -> None:
        super().__init__(payload)
        self._evidence_kind = evidence_kind
        self._evidence_context = dict(context)
        self._evidence_digest = _evidence_digest(self, evidence_kind, context)


def _evidence_digest(
    payload: Mapping[str, Any], evidence_kind: str, context: Mapping[str, Any]
) -> str:
    canonical = json.dumps(
        {
            "kind": evidence_kind,
            "context": dict(context),
            "payload": dict(payload),
        },
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hmac.new(_EVIDENCE_KEY, canonical, hashlib.sha256).hexdigest()


def _seal_trusted_evidence(
    payload: Mapping[str, Any], *, evidence_kind: str, context: Mapping[str, Any]
) -> _TrustedEvidence:
    return _TrustedEvidence(
        payload,
        evidence_kind=evidence_kind,
        context=context,
    )


def _trusted_evidence_context(
    payload: Mapping[str, Any], *, evidence_kind: str
) -> dict[str, Any] | None:
    if not isinstance(payload, _TrustedEvidence):
        return None
    if payload._evidence_kind != evidence_kind:
        return None
    expected = _evidence_digest(payload, evidence_kind, payload._evidence_context)
    if not hmac.compare_digest(payload._evidence_digest, expected):
        return None
    return dict(payload._evidence_context)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class SectionEvaluationConfig:
    """One bounded diagnostic section probe used by reconstruction evaluation.

    Coordinates and tolerance are millimetres, and ``samples_per_edge`` is an
    integer measurement control. Section IDs must be unique within an
    ``EvaluationConfig``. Section results are diagnostics, not acceptance gates.
    ``require_nonempty``, ``max_hausdorff``, and ``max_relative_area_error`` are
    deprecated compatibility inputs and do not affect stage status.
    """

    section_id: str
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]
    tolerance: float = 1.0e-7
    samples_per_edge: int = 16
    # Deprecated compatibility inputs. Section comparisons remain diagnostic.
    require_nonempty: bool = True
    max_hausdorff: float = 0.1
    max_relative_area_error: float = 0.01

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.section_id):
            raise ValueError("section_id must be a filename-safe token")
        if len(self.origin) != 3 or not all(
            _finite_number(value) for value in self.origin
        ):
            raise ValueError("origin must contain three finite values")
        if len(self.normal) != 3 or not all(
            _finite_number(value) for value in self.normal
        ):
            raise ValueError("normal must contain three finite values")
        if math.sqrt(sum(value * value for value in self.normal)) <= 1.0e-12:
            raise ValueError("normal must be non-zero")
        if not _finite_number(self.tolerance) or self.tolerance <= 0.0:
            raise ValueError("tolerance must be positive and finite")
        if isinstance(self.samples_per_edge, bool) or not isinstance(
            self.samples_per_edge, int
        ):
            raise TypeError("samples_per_edge must be an integer")
        if self.samples_per_edge < 4:
            raise ValueError("samples_per_edge must be at least four")
        if not isinstance(self.require_nonempty, bool):
            raise TypeError("require_nonempty must be a bool")
        for name in ("max_hausdorff", "max_relative_area_error"):
            value = getattr(self, name)
            if not _finite_number(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class EvaluationConfig:
    """Closed configuration contract for trusted reconstruction evaluation.

    Timeout fields are seconds. ``strict_material_tolerance`` is cubic
    millimetres, while boundary linear deflection and strict geometric tolerance
    are millimetres. ``boundary_max_samples`` is an integer measurement control.
    Paths and this configuration belong to the trusted evaluator; participant
    output must not be allowed to replace them. Aggregate and sampled metrics are
    diagnostic and have no acceptance thresholds. The ``global_max_*`` and
    ``boundary_max_*`` fields are deprecated compatibility inputs and are ignored.
    """

    target_kind: str = "solid"
    stage_timeout_seconds: float = 120.0
    material_timeout_seconds: float = 300.0
    # Deprecated compatibility inputs. These values are intentionally ignored;
    # aggregate and sampled metrics are diagnostic-only.
    global_max_bbox_delta: float = 0.1
    global_max_centroid_distance: float = 0.1
    global_max_relative_volume_error: float = 0.01
    global_max_relative_area_error: float = 0.01
    strict_material_tolerance: float = 1.0e-6
    boundary_linear_deflection: float = 0.2
    boundary_max_samples: int = 200
    boundary_max_hausdorff: float = 0.1
    boundary_max_p95: float = 0.1
    sections: tuple[SectionEvaluationConfig, ...] = ()
    strict_geometric_tolerance: float = 1.0e-7

    def __post_init__(self) -> None:
        if self.target_kind not in {"solid", "open_shell"}:
            raise ValueError("target_kind must be solid or open_shell")
        for name in ("stage_timeout_seconds", "material_timeout_seconds"):
            value = getattr(self, name)
            if not _finite_number(value) or value <= 0.0:
                raise ValueError(f"{name} must be positive and finite")
        for name in (
            "global_max_bbox_delta",
            "global_max_centroid_distance",
            "global_max_relative_volume_error",
            "global_max_relative_area_error",
            "boundary_max_hausdorff",
            "boundary_max_p95",
        ):
            value = getattr(self, name)
            if not _finite_number(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name in (
            "strict_material_tolerance",
            "boundary_linear_deflection",
            "strict_geometric_tolerance",
        ):
            value = getattr(self, name)
            if not _finite_number(value) or value <= 0.0:
                raise ValueError(f"{name} must be positive and finite")
        if isinstance(self.boundary_max_samples, bool) or not isinstance(
            self.boundary_max_samples, int
        ):
            raise TypeError("boundary_max_samples must be an integer")
        if self.boundary_max_samples < 16:
            raise ValueError("boundary_max_samples must be at least 16")
        if not isinstance(self.sections, tuple) or not all(
            isinstance(section, SectionEvaluationConfig) for section in self.sections
        ):
            raise TypeError("sections must be a tuple of SectionEvaluationConfig")
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section IDs must be unique")


def _relative_error(current: float, target: float) -> float:
    return abs(float(current) - float(target)) / max(abs(float(target)), 1.0e-12)


def _process_group_options() -> dict[str, Any]:
    if os.name == "nt":
        return {
            "creationflags": (subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED)
        }
    return {"start_new_session": True}


def _create_windows_job() -> int | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, ctypes.FormatError(error_code))
    return int(handle)


def _assign_process_to_windows_job(
    job_handle: int | None, process: subprocess.Popen[Any]
) -> None:
    if job_handle is None:
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    if not kernel32.AssignProcessToJobObject(job_handle, int(process._handle)):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, ctypes.FormatError(error_code))


def _resume_windows_process(
    job_handle: int | None, process: subprocess.Popen[Any]
) -> None:
    if job_handle is None:
        return
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = wintypes.LONG
    status = ntdll.NtResumeProcess(int(process._handle))
    if status < 0:
        raise OSError(f"failed to resume evaluation worker (NTSTATUS {status:#x})")


def _terminate_windows_job(job_handle: int | None) -> bool:
    if job_handle is None:
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    return bool(kernel32.TerminateJobObject(job_handle, 1))


def _close_windows_job(job_handle: int | None) -> None:
    if job_handle is None:
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job_handle)


def _terminate_process_tree(
    process: subprocess.Popen[Any], windows_job: int | None = None
) -> None:
    if os.name == "nt":
        if _terminate_windows_job(windows_job):
            try:
                process.wait(timeout=5.0)
                return
            except subprocess.TimeoutExpired:
                pass
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
        return

    descendant_pids: set[int] = set()
    try:
        listing = subprocess.run(
            ["ps", "-eo", "pid=,ppid="],
            capture_output=True,
            check=False,
            text=True,
            timeout=2.0,
        )
        children: dict[int, list[int]] = {}
        for line in listing.stdout.splitlines():
            values = line.split()
            if len(values) != 2:
                continue
            pid, parent_pid = map(int, values)
            children.setdefault(parent_pid, []).append(pid)
        pending = list(children.get(process.pid, ()))
        while pending:
            pid = pending.pop()
            if pid in descendant_pids:
                continue
            descendant_pids.add(pid)
            pending.extend(children.get(pid, ()))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        process.kill()
    for pid in descendant_pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


def _wait_after_termination(process: subprocess.Popen[Any]) -> None:
    try:
        process.wait(timeout=5.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=1.0)
        except (AttributeError, OSError, subprocess.TimeoutExpired):
            pass


def _stage(
    *,
    name: str,
    request: Mapping[str, Any],
    output_directory: Path,
    timeout_seconds: float,
    python_executable: str,
) -> dict[str, Any]:
    """Execute one OCP-heavy stage with a hard process-tree timeout."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("stage name must be a filename-safe token")
    if output_directory.is_symlink():
        raise ValueError("output_directory must not be a symbolic link")
    output_directory = output_directory.resolve()
    if not output_directory.is_dir():
        raise ValueError("output_directory must be an existing directory")
    stage_directory = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=output_directory))
    request_path = stage_directory / "request.json"
    report_path = stage_directory / "report.json"
    stdout_path = stage_directory / "stdout.log"
    stderr_path = stage_directory / "stderr.log"
    with request_path.open("x", encoding="utf-8") as request_stream:
        request_stream.write(json.dumps(dict(request), indent=2))
    started = time.perf_counter()
    trusted_src = Path(__file__).resolve().parents[3]
    bootstrap = (
        "import runpy,sys;"
        "sys.path.insert(0,sys.argv.pop(1));"
        "runpy.run_module('simplecadapi.inverse_engineer.brep.worker',"
        "run_name='__main__')"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PYTHONPATH", "PYTHONSTARTUP"}
    }
    environment["PYTHONUTF8"] = "1"
    windows_job: int | None = None
    process: subprocess.Popen[Any] | None = None
    with (
        stdout_path.open("w", encoding="utf-8") as stdout,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            try:
                windows_job = _create_windows_job()
                process = subprocess.Popen(
                    [
                        python_executable,
                        "-I",
                        "-c",
                        bootstrap,
                        str(trusted_src),
                        str(request_path),
                        str(report_path),
                    ],
                    cwd=trusted_src,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    **_process_group_options(),
                )
                _assign_process_to_windows_job(windows_job, process)
                _resume_windows_process(windows_job, process)
            except OSError as error:
                if process is not None:
                    _terminate_process_tree(process, windows_job)
                    _wait_after_termination(process)
                return {
                    "status": "error",
                    "gate_passed": False,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "report": None,
                    "report_path": None,
                    "error": f"evaluation stage failed to start: {error}",
                }
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate_process_tree(process, windows_job)
                _wait_after_termination(process)
                return {
                    "status": "error",
                    "gate_passed": False,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "report": None,
                    "report_path": None,
                    "error": f"evaluation stage timed out after {timeout_seconds} seconds",
                }
        finally:
            _close_windows_job(windows_job)
    assert process is not None
    elapsed = round(time.perf_counter() - started, 3)
    if process.returncode != 0:
        error = stderr_path.read_text(encoding="utf-8", errors="replace").strip()
        return {
            "status": "error",
            "gate_passed": False,
            "elapsed_seconds": elapsed,
            "report": None,
            "report_path": None,
            "error": error or f"worker exited with code {process.returncode}",
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "status": "error",
            "gate_passed": False,
            "elapsed_seconds": elapsed,
            "report": None,
            "report_path": None,
            "error": f"worker produced an invalid report: {error}",
        }
    return {
        "status": "completed",
        "gate_passed": None,
        "elapsed_seconds": elapsed,
        "report": report,
        "report_path": str(report_path),
        "error": None,
    }


def inspect_benchmark_step(
    path: str | Path,
    *,
    name: str,
    output_directory: str | Path,
    timeout_seconds: float,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Inspect one candidate or target STEP in a bounded trusted worker.

    The returned stage envelope has ``status`` (``passed``, ``failed``, or
    ``error``), boolean ``gate_passed``, ``elapsed_seconds``, ``report``,
    ``report_path``, and ``error``. A completed report contains ``valid`` and
    ``counts``; classification uses the integer ``solid`` and ``shell`` counts.
    Lengths are millimetres, area is square millimetres, volume is cubic
    millimetres, and elapsed time is seconds.

    The process is isolated from participant Python paths and a timeout kills its
    entire process tree. Only the unmodified process-local result of this trusted function may
    be supplied to ``classify_benchmark_result``; a participant-authored
    inspection report or claimed shape kind is not acceptance evidence.
    """

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    result = _stage(
        name=name,
        request={"task": "inspect", "current": str(Path(path).resolve())},
        output_directory=output,
        timeout_seconds=timeout_seconds,
        python_executable=python_executable,
    )
    if result["status"] == "completed":
        report = result["report"]
        result["gate_passed"] = bool(report.get("valid"))
        result["status"] = "passed" if result["gate_passed"] else "failed"
    return _seal_trusted_evidence(
        result,
        evidence_kind="inspection",
        context={
            "candidate_path": str(Path(path).resolve()),
            "candidate_sha256": _file_sha256(path),
        },
    )


def _finalize_stage(
    result: dict[str, Any], checks: Mapping[str, bool]
) -> dict[str, Any]:
    if result["status"] == "error":
        return result
    result["checks"] = dict(checks)
    result["gate_passed"] = all(checks.values())
    result["status"] = "passed" if result["gate_passed"] else "failed"
    return result


def _strict_material_equal(report: Mapping[str, Any], tolerance: float) -> bool:
    volume_balance = report.get("volume_balance")
    return bool(
        report.get("method") == "bidirectional_cut"
        and report.get("strict_equality_supported") is True
        and report.get("boolean_result_valid") is True
        and isinstance(volume_balance, Mapping)
        and volume_balance.get("valid") is True
        and float(report["missing_material"]["volume"]) < tolerance
        and float(report["excess_material"]["volume"]) < tolerance
    )


def run_comparison_bundle(
    config: EvaluationConfig,
    *,
    target_path: str | Path,
    candidate_path: str | Path,
    output_directory: str | Path,
    diagnostics: bool = False,
    strict_topology: bool = False,
    python_executable: str = sys.executable,
) -> dict[str, dict[str, Any]]:
    """Run trusted acceptance stages and optional geometric diagnostics.

    Worker-stage envelopes contain ``status``, ``gate_passed``,
    ``elapsed_seconds``, ``report``, ``report_path``, and ``error``. Successful
    diagnostics have status ``completed``, ``gate_passed=None``, and no
    acceptance checks. Completed material and strict acceptance stages add
    boolean ``checks`` and become ``passed`` or ``failed``. Non-run stages contain
    a ``reason`` instead; the aggregate ``sections`` stage contains ``reports``,
    one worker envelope per unique section ID. ``global`` and ``material`` always
    appear; ``boundary`` and ``sections`` appear only when ``diagnostics=True``;
    ``strict`` always appears but runs only for a solid with proven material
    equality when ``strict_topology=True``.

    Report schemas and units:

    - ``global`` reports bounding-box and centroid distances in millimetres,
      total surface area in square millimetres, aggregate volume in cubic
      millimetres, topology counts, and dimensionless relative deltas.
    - ``material`` reports the comparison method, directional missing/excess
      volumes in cubic millimetres, Boolean and volume-balance validity, and the
      derived ``strict_point_set_equal`` tri-state. Its
      ``relative_total_difference`` is dimensionless and diagnostic. For regular
      solids, non-fuzzy bidirectional Cut residual volumes establish
      tolerance-bounded material equivalence; this is not an aggregate
      mass-property comparison and does not prove topology, representation, or
      literal boundary identity.
    - ``boundary`` reports sampled-to-exact distances in millimetres, including
      approximate Hausdorff and p95 distances. It is diagnostic, never equality
      proof.
    - ``sections`` contains one envelope per configured section. Plane values,
      perimeters, and Hausdorff distances are millimetres; section areas are
      square millimetres; ``relative_area_error`` is dimensionless.
    - ``strict`` reports directional difference volumes in cubic millimetres,
      geometric and Boolean tolerances, STEP validity, geometric point-set
      equality, geometry-labelled incidence isomorphism, and
      ``hard_gate_passed``. Exact classification also requires the trusted
      envelope's ``checks.hard_gate`` to be true.

    The evaluator configuration, target/candidate paths, worker executable, and
    returned reports are trusted-harness data. Participant-authored reports or
    edited stage envelopes must never be passed to classification. Aggregate
    global properties, sampled boundary distances, and bounded section probes are
    diagnostics and never affect classification. Only strict bidirectional
    material residual evidence and, when requested, strict topology evidence are
    acceptance gates.
    """

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    target = str(Path(target_path).resolve())
    current = str(Path(candidate_path).resolve())
    stages: dict[str, dict[str, Any]] = {}

    global_stage = _stage(
        name="global",
        request={"task": "global", "target": target, "current": current},
        output_directory=output,
        timeout_seconds=config.stage_timeout_seconds,
        python_executable=python_executable,
    )
    global_stage["gate_passed"] = None
    stages["global"] = global_stage

    if config.target_kind == "solid":
        material_stage = _stage(
            name="material",
            request={
                "task": "material",
                "target": target,
                "current": current,
                "options": {
                    "boolean_tolerance": None,
                    "include_components": True,
                },
            },
            output_directory=output,
            timeout_seconds=config.material_timeout_seconds,
            python_executable=python_executable,
        )
        if material_stage["status"] != "error":
            report = material_stage["report"]
            global_report = stages["global"].get("report")
            volume_report = (
                global_report.get("volume")
                if isinstance(global_report, Mapping)
                else None
            )
            target_volume = (
                volume_report.get("target")
                if isinstance(volume_report, Mapping)
                else None
            )
            relative = (
                (
                    float(report["missing_material"]["volume"])
                    + float(report["excess_material"]["volume"])
                )
                / max(float(target_volume), 1.0e-12)
                if target_volume is not None
                else None
            )
            strict_equal = _strict_material_equal(
                report, config.strict_material_tolerance
            )
            strict_supported = bool(
                report.get("method") == "bidirectional_cut"
                and report.get("strict_equality_supported") is True
                and report.get("boolean_result_valid") is True
                and report.get("volume_balance", {}).get("valid") is True
            )
            material_stage["relative_total_difference"] = relative
            material_stage["strict_point_set_equal"] = (
                strict_equal if strict_supported else None
            )
            material_stage = _finalize_stage(
                material_stage,
                {
                    "boolean_result_valid": report.get("boolean_result_valid") is True,
                    "strict_equality_supported": report.get("strict_equality_supported")
                    is True,
                    "volume_balance_valid": report.get("volume_balance", {}).get(
                        "valid"
                    )
                    is True,
                    "strict_missing_material": float(
                        report["missing_material"]["volume"]
                    )
                    < config.strict_material_tolerance,
                    "strict_excess_material": float(report["excess_material"]["volume"])
                    < config.strict_material_tolerance,
                },
            )
    else:
        material_stage = {
            "status": "not_applicable",
            "gate_passed": True,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "open-shell targets have no solid material point set",
            "strict_point_set_equal": None,
        }
    stages["material"] = material_stage

    if diagnostics:
        boundary_stage = _stage(
            name="boundary",
            request={
                "task": "boundary",
                "target": target,
                "current": current,
                "options": {
                    "linear_deflection": config.boundary_linear_deflection,
                    "max_samples": config.boundary_max_samples,
                },
            },
            output_directory=output,
            timeout_seconds=config.stage_timeout_seconds,
            python_executable=python_executable,
        )
        boundary_stage["gate_passed"] = None
        stages["boundary"] = boundary_stage

        section_results = []
        for section in config.sections:
            section_stage = _stage(
                name=f"section-{section.section_id}",
                request={
                    "task": "section",
                    "target": target,
                    "current": current,
                    "options": {
                        "plane_origin": section.origin,
                        "plane_normal": section.normal,
                        "tolerance": section.tolerance,
                        "samples_per_edge": section.samples_per_edge,
                    },
                },
                output_directory=output,
                timeout_seconds=config.stage_timeout_seconds,
                python_executable=python_executable,
            )
            section_stage["gate_passed"] = None
            if section_stage["status"] != "error":
                report = section_stage["report"]
                target_area = float(report["target"]["material_area"])
                section_stage["relative_area_error"] = _relative_error(
                    report["current"]["material_area"], target_area
                )
            section_stage["section_id"] = section.section_id
            section_results.append(section_stage)
        stages["sections"] = {
            "status": (
                "error"
                if any(item["status"] == "error" for item in section_results)
                else "completed"
            ),
            "gate_passed": None,
            "elapsed_seconds": round(
                sum(item["elapsed_seconds"] for item in section_results), 3
            ),
            "reports": section_results,
            "error": next(
                (item["error"] for item in section_results if item.get("error")),
                None,
            ),
        }

    strict_material_equal = material_stage.get("strict_point_set_equal") is True
    if config.target_kind != "solid":
        strict_stage = {
            "status": "not_applicable",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "open-shell boundary-set equality is not implemented",
        }
    elif not strict_topology:
        strict_stage = {
            "status": "skipped",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "strict topology comparison was not requested",
        }
    elif not strict_material_equal:
        strict_stage = {
            "status": "skipped",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "strict topology requires proven material equality",
        }
    else:
        strict_stage = _stage(
            name="strict",
            request={
                "task": "strict",
                "target": target,
                "current": current,
                "options": {
                    "geometric_tolerance": config.strict_geometric_tolerance,
                    "boolean_volume_tolerance": config.strict_material_tolerance,
                    "boolean_fuzzy_tolerance": None,
                },
            },
            output_directory=output,
            timeout_seconds=config.stage_timeout_seconds,
            python_executable=python_executable,
        )
        if strict_stage["status"] != "error":
            strict_stage = _finalize_stage(
                strict_stage,
                {"hard_gate": bool(strict_stage["report"]["hard_gate_passed"])},
            )
    stages["strict"] = strict_stage
    return _seal_trusted_evidence(
        stages,
        evidence_kind="comparison_bundle",
        context={
            "target_path": target,
            "target_sha256": _file_sha256(target),
            "candidate_path": current,
            "candidate_sha256": _file_sha256(current),
            "config": asdict(config),
            "diagnostics": bool(diagnostics),
            "strict_topology": bool(strict_topology),
        },
    )


_INSPECTION_COUNT_KEYS = (
    "solid",
    "shell",
    "open_shell",
    "closed_shell",
    "face_occurrences",
    "edge_occurrences",
    "vertex_occurrences",
    "unique_faces",
    "unique_edges",
    "unique_vertices",
)


def _trusted_candidate_facts(
    inspection: Mapping[str, Any],
) -> tuple[bool, int, int, int, int]:
    report = inspection.get("report")
    if (
        inspection.get("status") != "passed"
        or inspection.get("gate_passed") is not True
        or not isinstance(report, Mapping)
        or report.get("valid") is not True
        or not isinstance(report.get("source"), str)
        or not report["source"]
    ):
        return False, 0, 0, 0, 0
    counts = report.get("counts")
    if not isinstance(counts, Mapping) or not all(
        isinstance(counts.get(key), int)
        and not isinstance(counts.get(key), bool)
        and counts[key] >= 0
        for key in _INSPECTION_COUNT_KEYS
    ):
        return False, 0, 0, 0, 0
    if counts["open_shell"] + counts["closed_shell"] != counts["shell"]:
        return False, 0, 0, 0, 0
    return (
        True,
        counts["solid"],
        counts["shell"],
        counts["open_shell"],
        counts["unique_faces"],
    )


def _finite_nonnegative_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0.0
    )


def _strict_report_proves_exact(stage: Mapping[str, Any]) -> bool:
    report = stage.get("report")
    if (
        stage.get("status") != "passed"
        or stage.get("gate_passed") is not True
        or not isinstance(report, Mapping)
    ):
        return False
    tolerance = report.get("boolean_volume_tolerance")
    diagnostics = report.get("diagnostics")
    validity = (
        diagnostics.get("step_validity", {}) if isinstance(diagnostics, Mapping) else {}
    )
    graph_counts = (
        report.get("target_graph_nodes_edges"),
        report.get("candidate_graph_nodes_edges"),
    )
    target_counts = (
        diagnostics.get("topology_counts", {}).get("target")
        if isinstance(diagnostics, Mapping)
        else None
    )
    candidate_counts = (
        diagnostics.get("topology_counts", {}).get("candidate")
        if isinstance(diagnostics, Mapping)
        else None
    )
    checks = stage.get("checks")
    return bool(
        _finite_nonnegative_number(tolerance)
        and tolerance > 0.0
        and _finite_nonnegative_number(report.get("geometric_tolerance"))
        and report["geometric_tolerance"] > 0.0
        and _finite_nonnegative_number(report.get("target_minus_candidate_volume"))
        and report["target_minus_candidate_volume"] < tolerance
        and _finite_nonnegative_number(report.get("candidate_minus_target_volume"))
        and report["candidate_minus_target_volume"] < tolerance
        and report.get("same_geometric_point_set") is True
        and report.get("geometry_labelled_incidence_graph_isomorphic") is True
        and report.get("hard_gate_passed") is True
        and isinstance(checks, Mapping)
        and checks.get("hard_gate") is True
        and isinstance(validity, Mapping)
        and validity.get("target") is True
        and validity.get("candidate") is True
        and all(
            isinstance(counts, (list, tuple))
            and len(counts) == 2
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in counts
            )
            for counts in graph_counts
        )
        and isinstance(target_counts, Mapping)
        and isinstance(candidate_counts, Mapping)
        and all(
            isinstance(counts.get(key), int)
            and not isinstance(counts.get(key), bool)
            and counts[key] >= 0
            for counts in (target_counts, candidate_counts)
            for key in ("face", "edge", "vertex")
        )
        and graph_counts[0][0]
        == target_counts["face"] + target_counts["edge"] + target_counts["vertex"]
        and graph_counts[1][0]
        == candidate_counts["face"]
        + candidate_counts["edge"]
        + candidate_counts["vertex"]
        and tuple(graph_counts[0]) == tuple(graph_counts[1])
    )


def _strict_report_disproves_topology(stage: Mapping[str, Any]) -> bool:
    report = stage.get("report")
    return bool(
        stage.get("status") == "failed"
        and isinstance(report, Mapping)
        and report.get("same_geometric_point_set") is True
        and report.get("geometry_labelled_incidence_graph_isomorphic") is False
        and report.get("hard_gate_passed") is False
    )


def classify_benchmark_result(
    *,
    replay_succeeded: bool,
    persistence_succeeded: bool,
    baseline_integrity_passed: bool,
    candidate_bytes_equal_target: bool,
    target_kind: str,
    candidate_inspection: Mapping[str, Any],
    stages: Mapping[str, Mapping[str, Any]],
    strict_topology_requested: bool,
    parameter_representation_required: bool,
    parameter_representation_passed: bool | None,
) -> dict[str, Any]:
    """Classify trusted evidence without erasing a proven lower tier.

    ``candidate_inspection`` must be the unmodified, process-local result of
    ``inspect_benchmark_step``. Candidate validity and solid/shell kind are
    derived from its completed strict-schema report, never from participant
    claims. Open-shell classification requires zero solids, at least one shell
    explicitly reported open, and at least one unique face. ``stages`` must likewise be the unmodified,
    process-local output of ``run_comparison_bundle``. Both results bind the
    evaluated paths and SHA-256 digests, so replacing either STEP invalidates
    the evidence. ``exact_brep`` requires the strict report's
    validity, directional-volume, point-set, and incidence evidence, not just a
    claimed stage status. It also requires the trusted envelope's
    ``checks.hard_gate``. Parameter-representation evidence is supplied by the
    trusted case harness when that additional gate is required. Global
    properties, sampled boundary distances, and bounded section probes are
    diagnostics and are ignored by classification.

    The result schema is ``{"classification": str, "reasons": list[str]}``.
    Classifications are ``unsupported_or_incomplete``, ``approximation``,
    ``geometry_equivalent``, and ``exact_brep``. This function performs no CAD
    work and all ratios, distances, and volumes retain the units documented by
    ``run_comparison_bundle``.
    """

    if target_kind not in {"solid", "open_shell"}:
        raise ValueError("target_kind must be solid or open_shell")
    inspection_context = _trusted_evidence_context(
        candidate_inspection,
        evidence_kind="inspection",
    )
    stages_context = _trusted_evidence_context(
        stages,
        evidence_kind="comparison_bundle",
    )
    (
        candidate_valid,
        candidate_solid_count,
        candidate_shell_count,
        candidate_open_shell_count,
        candidate_face_count,
    ) = _trusted_candidate_facts(candidate_inspection)

    reasons = []
    if not replay_succeeded:
        reasons.append("replay_failed")
    if not persistence_succeeded:
        reasons.append("step_persistence_failed")
    if not baseline_integrity_passed:
        reasons.append("baseline_integrity_failed")
    if candidate_bytes_equal_target:
        reasons.append("candidate_bytes_equal_target")
    if inspection_context is None:
        reasons.append("candidate_inspection_untrusted")
    elif not candidate_valid:
        reasons.append("candidate_invalid")
    if inspection_context is not None and candidate_valid:
        if target_kind == "open_shell" and candidate_solid_count:
            reasons.append("fabricated_solid_for_open_shell")
        elif target_kind == "solid" and not candidate_solid_count:
            reasons.append("candidate_kind_mismatch")
        elif target_kind == "open_shell" and (
            not candidate_shell_count
            or candidate_solid_count
            or not candidate_open_shell_count
            or not candidate_face_count
        ):
            reasons.append("candidate_kind_mismatch")
    if reasons:
        return {"classification": "unsupported_or_incomplete", "reasons": reasons}

    if stages_context is None:
        return {
            "classification": "approximation",
            "reasons": ["comparison_evidence_untrusted"],
        }
    if stages_context.get("candidate_path") != inspection_context.get(
        "candidate_path"
    ) or stages_context.get("candidate_sha256") != inspection_context.get(
        "candidate_sha256"
    ) or stages_context.get("config", {}).get("target_kind") != target_kind:
        return {
            "classification": "approximation",
            "reasons": ["comparison_evidence_context_mismatch"],
        }
    candidate_path = stages_context["candidate_path"]
    target_path = stages_context["target_path"]
    try:
        content_unchanged = (
            _file_sha256(candidate_path) == stages_context["candidate_sha256"]
            and _file_sha256(target_path) == stages_context["target_sha256"]
        )
    except OSError:
        content_unchanged = False
    if not content_unchanged:
        return {
            "classification": "approximation",
            "reasons": ["comparison_evidence_inputs_changed"],
        }

    if target_kind == "open_shell":
        return {
            "classification": "approximation",
            "reasons": ["open_shell_equivalence_unproved"],
        }

    material = stages.get("material", {})
    strict_material = (
        True
        if material.get("status") == "passed"
        and material.get("gate_passed") is True
        and material.get("strict_point_set_equal") is True
        else False if material.get("strict_point_set_equal") is False else None
    )
    if strict_material is not True:
        return {
            "classification": "approximation",
            "reasons": [
                (
                    "strict_material_point_set_differs"
                    if strict_material is False
                    else "strict_material_equality_unproved"
                )
            ],
        }
    if not strict_topology_requested:
        return {
            "classification": "geometry_equivalent",
            "reasons": ["strict_topology_not_requested"],
        }

    strict = stages.get("strict", {})
    if _strict_report_proves_exact(strict):
        if parameter_representation_required:
            if parameter_representation_passed is True:
                return {"classification": "exact_brep", "reasons": []}
            return {
                "classification": "geometry_equivalent",
                "reasons": [
                    (
                        "parameter_representation_differs"
                        if parameter_representation_passed is False
                        else "parameter_representation_unproved"
                    )
                ],
            }
        return {"classification": "exact_brep", "reasons": []}
    if _strict_report_disproves_topology(strict):
        return {
            "classification": "geometry_equivalent",
            "reasons": ["strict_topology_differs"],
        }
    if strict.get("status") == "failed" and isinstance(strict.get("report"), Mapping):
        return {
            "classification": "geometry_equivalent",
            "reasons": ["strict_stage_conflicts_with_material_proof"],
        }
    return {
        "classification": "geometry_equivalent",
        "reasons": ["strict_topology_unproved"],
    }


__all__ = [
    "EvaluationConfig",
    "SectionEvaluationConfig",
    "classify_benchmark_result",
    "inspect_benchmark_step",
    "run_comparison_bundle",
]
