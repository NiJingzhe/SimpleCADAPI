"""Run every current example model in an isolated process and export scenes.

This is intentionally a disposable harness for the example tagging migration.
It uses the model list from ``test_example_model_contract`` so the execution
set stays aligned with the repository's structural contract.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_HEAVY_TIMEOUT_SECONDS = 1800
HEAVY_CASES = {
    "examples/16_compact_two_stage_planetary_reducer/main.py",
    "examples/20_integrated_bldc_joint_actuator/main.py",
}


def _is_model_decorator(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "scad"
        and node.attr == "model"
    ) or (isinstance(node, ast.Name) and node.id == "model")


def _builder_name(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    model_functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_is_model_decorator(decorator) for decorator in node.decorator_list)
    ]
    if len(model_functions) != 1:
        raise RuntimeError(f"expected one @model entry in {path}, got {model_functions}")
    return model_functions[0]


def _model_cases() -> list[tuple[str, str]]:
    contract_path = ROOT / "test" / "test_example_model_contract.py"
    spec = importlib.util.spec_from_file_location(
        "simplecadapi_example_model_contract", contract_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load model contract: {contract_path}")
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)

    cases = []
    for path in contract._model_files():
        relative_path = path.resolve().relative_to(ROOT).as_posix()
        cases.append((relative_path, _builder_name(path)))
    return cases


def _child_main(relative_path: str, builder_name: str, output_dir: Path) -> None:
    path = (ROOT / relative_path).resolve()
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(
        f"simplecadapi_scene_case_{os.getpid()}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load example module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, builder_name)
    result = builder()
    exported = result.export_artifacts(output_dir=output_dir)
    print(
        "SCENE_RUN_RESULT="
        + json.dumps(
            {
                "graph_id": exported.session.graph.graph_id,
                "artifact_paths": {
                    key: str(value) for key, value in exported.artifact_paths.items()
                },
                "result_node_count": len(exported.result_node_ids),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_case(
    *,
    relative_path: str,
    builder_name: str,
    run_dir: Path,
    timeout_seconds: int,
    heavy_timeout_seconds: int,
) -> dict[str, Any]:
    case_name = relative_path.removesuffix(".py").replace("/", "__")
    case_dir = run_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (case_dir / f"stdout.attempt-{attempt}.log").exists():
        attempt += 1
    for log_name in ("stdout.log", "stderr.log"):
        log_path = case_dir / log_name
        if log_path.exists():
            log_path.replace(
                case_dir / f"{log_path.stem}.attempt-{attempt}{log_path.suffix}"
            )
    timeout = (
        heavy_timeout_seconds
        if relative_path in HEAVY_CASES
        else timeout_seconds
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        relative_path,
        builder_name,
        str(case_dir),
    ]
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    print(
        f"[scene-export] starting {relative_path}::{builder_name} "
        f"timeout={timeout}s",
        flush=True,
    )
    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    error: str | None = None
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
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            _kill_process_group(process)
            stdout, stderr = process.communicate()
            if exc.stdout:
                stdout = str(exc.stdout)
            if exc.stderr:
                stderr = str(exc.stderr)
    except Exception as exc:  # pragma: no cover - harness failure path
        error = f"{exc.__class__.__name__}: {exc}"

    elapsed = time.monotonic() - started
    (case_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (case_dir / "stderr.log").write_text(stderr, encoding="utf-8")
    scene_paths = sorted(case_dir.glob("*.scene.zip"))
    child_result: dict[str, Any] | None = None
    for line in stdout.splitlines():
        if line.startswith("SCENE_RUN_RESULT="):
            try:
                child_result = json.loads(line.removeprefix("SCENE_RUN_RESULT="))
            except json.JSONDecodeError:
                error = "invalid SCENE_RUN_RESULT payload"

    status = "passed"
    if timed_out:
        status = "timeout"
    elif error is not None or returncode != 0:
        status = "failed"
    elif len(scene_paths) != 1:
        status = "failed"
        error = f"expected one scene zip, found {len(scene_paths)}"

    record = {
        "case": relative_path,
        "builder": builder_name,
        "case_dir": str(case_dir.relative_to(ROOT)),
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "elapsed_seconds": round(elapsed, 3),
        "started_at": started_at.isoformat(),
        "stdout_log": str((case_dir / "stdout.log").relative_to(ROOT)),
        "stderr_log": str((case_dir / "stderr.log").relative_to(ROOT)),
        "scene_paths": [str(path.relative_to(ROOT)) for path in scene_paths],
        "child_result": child_result,
        "error": error,
        "attempt": attempt,
    }
    print(
        f"[scene-export] {status} {relative_path} elapsed={elapsed:.1f}s",
        flush=True,
    )
    return record


def _publish_scenes(
    run_dir: Path,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scene_dir = run_dir / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    for existing in scene_dir.glob("*.scene.zip"):
        existing.unlink()
    published: list[dict[str, Any]] = []
    for record in records:
        scene_paths = record.get("scene_paths", [])
        if record.get("status") != "passed" or len(scene_paths) != 1:
            continue
        case_path = Path(record["case"])
        case_name = (
            case_path.parent.name if case_path.name == "main.py" else case_path.stem
        )
        source_path = ROOT / scene_paths[0]
        destination = scene_dir / f"{case_name}.scene.zip"
        shutil.copy2(source_path, destination)
        published.append(
            {
                "case": record["case"],
                "path": str(destination.relative_to(ROOT)),
            }
        )
    return published


def _parent_main(args: argparse.Namespace) -> int:
    all_cases = _model_cases()
    previous_records: dict[str, dict[str, Any]] = {}
    if args.resume is not None:
        run_dir = args.resume.resolve()
        report_path = run_dir / "execution_report.json"
        previous_report = json.loads(report_path.read_text(encoding="utf-8"))
        run_id = str(previous_report["run_id"])
        started_at = datetime.fromisoformat(previous_report["started_at"])
        previous_records = {
            record["case"]: record for record in previous_report["cases"]
        }
        cases = [
            case
            for case in all_cases
            if previous_records.get(case[0], {}).get("status") != "passed"
        ]
        print(
            f"[scene-export] resuming {run_id}; retrying {len(cases)} cases",
            flush=True,
        )
    else:
        cases = all_cases
        run_id = datetime.now(timezone.utc).strftime("scene_export_%Y%m%dT%H%M%SZ")
        run_dir = EXAMPLES / "out" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        started_at = datetime.now(timezone.utc)
    if args.case:
        requested = set(args.case)
        cases = [case for case in cases if case[0] in requested]
        unknown = requested - {case[0] for case in all_cases}
        if unknown:
            raise ValueError(f"unknown example cases: {sorted(unknown)}")
    if args.publish_only:
        cases = []
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _run_case,
                relative_path=relative_path,
                builder_name=builder_name,
                run_dir=run_dir,
                timeout_seconds=args.timeout,
                heavy_timeout_seconds=args.heavy_timeout,
            ): (relative_path, builder_name)
            for relative_path, builder_name in cases
        }
        for future in as_completed(futures):
            relative_path, builder_name = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:  # pragma: no cover - harness failure path
                records.append(
                    {
                        "case": relative_path,
                        "builder": builder_name,
                        "status": "failed",
                        "error": f"runner worker {exc.__class__.__name__}: {exc}",
                    }
                )

    records_by_case = dict(previous_records)
    records_by_case.update({record["case"]: record for record in records})
    records = sorted(records_by_case.values(), key=lambda record: record["case"])
    report = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "workers": args.workers,
        "timeout_seconds": args.timeout,
        "heavy_timeout_seconds": args.heavy_timeout,
        "case_count": len(all_cases),
        "passed": sum(record.get("status") == "passed" for record in records),
        "failed": sum(record.get("status") == "failed" for record in records),
        "timed_out": sum(record.get("status") == "timeout" for record in records),
        "cases": records,
    }
    report_path = run_dir / "execution_report.json"
    manifest_path = run_dir / "manifest.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    published_scenes = _publish_scenes(run_dir, records)
    manifest = {
        "run_id": run_id,
        "case_count": len(all_cases),
        "successful_scene_count": len(published_scenes),
        "standalone_scene_packages": published_scenes,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"[scene-export] report={report_path}", flush=True)
    print(f"[scene-export] scenes={run_dir / 'scenes'}", flush=True)
    print(
        f"[scene-export] passed={report['passed']} failed={report['failed']} "
        f"timed_out={report['timed_out']}",
        flush=True,
    )
    return 0 if report["failed"] == 0 and report["timed_out"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=3, metavar=("PATH", "BUILDER", "OUTPUT"))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--case", action="append")
    parser.add_argument("--publish-only", action="store_true")
    parser.add_argument(
        "--heavy-timeout", type=int, default=DEFAULT_HEAVY_TIMEOUT_SECONDS
    )
    args = parser.parse_args()
    if args.child:
        relative_path, builder_name, output = args.child
        _child_main(relative_path, builder_name, Path(output).resolve())
        return 0
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.publish_only and args.resume is None:
        parser.error("--publish-only requires --resume")
    return _parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
