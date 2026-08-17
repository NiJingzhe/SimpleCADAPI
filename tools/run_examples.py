"""Run every documented example and validate each emitted product package."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

import simplecadapi as scad
from simplecadapi.scene import read_scene_package


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_HEAVY_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True, slots=True)
class ExampleCase:
    path: str
    package_path: str
    args: tuple[str, ...] = ()
    heavy: bool = False

    @property
    def step_path(self) -> str:
        return str(Path(self.package_path).with_suffix(".step"))

    @property
    def fcstd_path(self) -> str:
        return str(Path(self.package_path).with_suffix(".FCStd"))

    @property
    def output_paths(self) -> tuple[str, str, str]:
        return (self.package_path, self.step_path, self.fcstd_path)


CASES = (
    ExampleCase(
        "examples/04_dimension_tolerance_chain.py",
        "examples/out/dimension_tolerance_chain/dimension_tolerance_chain.scadpkg",
    ),
    ExampleCase(
        "examples/08_constrained_sketch.py",
        "examples/out/constrained_sketch/constrained_sketch.scadpkg",
        heavy=True,
    ),
    ExampleCase(
        "examples/09_naca0016_blade_freecad.py",
        "examples/out/naca0016_blade/naca0016_blade.scadpkg",
        heavy=True,
    ),
    ExampleCase(
        "examples/10_part_assembly.py",
        "examples/out/hydraulic_rod_assembly/hydraulic_rod_assembly.scadpkg",
        heavy=True,
    ),
    ExampleCase(
        "examples/11_external_reference_gear_train.py",
        "examples/out/external_reference_gear_train/"
        "nested_external_reference_gear_trains.scadpkg",
    ),
    ExampleCase(
        "examples/7ep_caplcd_enclosure.py",
        "examples/out/7ep_caplcd_enclosure/caplcd_enclosure_7ep.scadpkg",
    ),
    ExampleCase(
        "examples/16_compact_two_stage_planetary_reducer/main.py",
        "examples/out/compact_two_stage_planetary_reducer/"
        "compact_two_stage_planetary_reducer.scadpkg",
        heavy=True,
    ),
    ExampleCase(
        "examples/20_integrated_bldc_joint_actuator/main.py",
        "examples/out/integrated_bldc_joint_actuator/"
        "integrated_bldc_joint_actuator.scadpkg",
        heavy=True,
    ),
)


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _inspect_product_package(path: Path) -> dict[str, Any]:
    package = scad.read_product_package(path)
    scene = read_scene_package(package.scene_bytes)
    manifest = package.manifest
    scene_manifest = scene.manifest
    if manifest["schema_version"] != "2.0":
        raise ValueError("product package is not schema 2.0")
    if scene_manifest["schema_version"] != "2.0":
        raise ValueError("embedded scene is not schema 2.0")
    if len(scene_manifest["product_assets"]) != len(manifest["objects"]):
        raise ValueError("embedded scene definition closure is incomplete")
    if not scene_manifest["feature_graph_assets"]:
        raise ValueError("embedded scene has no feature graph assets")
    if not scene_manifest["source_assets"]:
        raise ValueError("embedded scene has no source assets")
    return {
        "path": str(path.relative_to(ROOT)),
        "byte_length": path.stat().st_size,
        "content_hash": manifest["content_hash"],
        "root_definition_id": package.root_definition.definition_id,
        "root_definition_kind": package.root_definition.definition_kind,
        "definition_count": len(manifest["objects"]),
        "feature_graph_asset_count": len(scene_manifest["feature_graph_assets"]),
        "feature_count": len(scene_manifest["feature_index"]),
        "source_asset_count": len(scene_manifest["source_assets"]),
        "source_index_count": len(scene_manifest["source_index"]),
    }


def _case_directory(run_dir: Path, case: ExampleCase) -> Path:
    return run_dir / case.path.removesuffix(".py").replace("/", "__")


def _run_case(
    case: ExampleCase,
    *,
    run_dir: Path,
    timeout_seconds: int,
    heavy_timeout_seconds: int,
) -> dict[str, Any]:
    case_dir = _case_directory(run_dir, case)
    case_dir.mkdir(parents=True, exist_ok=True)
    timeout = heavy_timeout_seconds if case.heavy else timeout_seconds
    command = [sys.executable, case.path, *case.args]
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    output_paths = tuple(ROOT / path for path in case.output_paths)
    previous_output_mtimes = {
        path: path.stat().st_mtime_ns if path.exists() else None
        for path in output_paths
    }
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    print(f"[examples] starting {case.path} timeout={timeout}s", flush=True)
    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    error: str | None = None
    package_inspection: dict[str, Any] | None = None
    export_inspection: dict[str, dict[str, Any]] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(process)
            stdout, stderr = process.communicate()
    except Exception as exc:  # pragma: no cover - runner failure path
        error = f"{exc.__class__.__name__}: {exc}"

    if returncode == 0 and not timed_out and error is None:
        try:
            for output_path in output_paths:
                if not output_path.is_file():
                    raise FileNotFoundError(f"expected example artifact: {output_path}")
                if output_path.stat().st_size <= 0:
                    raise RuntimeError(f"example artifact is empty: {output_path}")
                previous_mtime = previous_output_mtimes[output_path]
                if (
                    previous_mtime is not None
                    and output_path.stat().st_mtime_ns <= previous_mtime
                ):
                    raise RuntimeError(
                        f"example artifact was not rewritten by this run: {output_path}"
                    )
            package_path = output_paths[0]
            export_inspection = {
                output_path.suffix: {
                    "path": str(output_path.relative_to(ROOT)),
                    "byte_length": output_path.stat().st_size,
                }
                for output_path in output_paths[1:]
            }
            package_inspection = _inspect_product_package(package_path)
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"

    elapsed = time.monotonic() - started
    (case_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (case_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    status = "passed"
    if timed_out:
        status = "timeout"
    elif error is not None or returncode != 0:
        status = "failed"
    record = {
        "case": case.path,
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "elapsed_seconds": round(elapsed, 3),
        "started_at": started_at.isoformat(),
        "stdout_log": str((case_dir / "stdout.log").relative_to(ROOT)),
        "stderr_log": str((case_dir / "stderr.log").relative_to(ROOT)),
        "package": package_inspection,
        "exports": export_inspection,
        "error": error,
    }
    print(f"[examples] {status} {case.path} elapsed={elapsed:.1f}s", flush=True)
    return record


def _run_all(args: argparse.Namespace) -> int:
    all_cases = {case.path: case for case in CASES}
    selected = list(CASES)
    if args.case:
        unknown = set(args.case) - set(all_cases)
        if unknown:
            raise ValueError(f"unknown example cases: {sorted(unknown)}")
        selected = [all_cases[path] for path in args.case]
    run_id = datetime.now(timezone.utc).strftime("examples_%Y%m%dT%H%M%SZ")
    run_dir = EXAMPLES / "out" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _run_case,
                case,
                run_dir=run_dir,
                timeout_seconds=args.timeout,
                heavy_timeout_seconds=args.heavy_timeout,
            ): case
            for case in selected
        }
        for future in as_completed(futures):
            case = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:  # pragma: no cover - runner failure path
                records.append(
                    {
                        "case": case.path,
                        "status": "failed",
                        "error": f"runner worker {exc.__class__.__name__}: {exc}",
                    }
                )
    records.sort(key=lambda record: record["case"])
    report = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "case_count": len(selected),
        "passed": sum(record["status"] == "passed" for record in records),
        "failed": sum(record["status"] == "failed" for record in records),
        "timed_out": sum(record["status"] == "timeout" for record in records),
        "cases": records,
    }
    report_path = run_dir / "execution_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"[examples] report={report_path}", flush=True)
    print(
        f"[examples] passed={report['passed']} failed={report['failed']} "
        f"timed_out={report['timed_out']}",
        flush=True,
    )
    return 0 if report["failed"] == 0 and report["timed_out"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--heavy-timeout", type=int, default=DEFAULT_HEAVY_TIMEOUT_SECONDS
    )
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return _run_all(args)


if __name__ == "__main__":
    raise SystemExit(main())
