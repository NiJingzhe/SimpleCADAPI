"""Command-line export of validated ``.scadpkg`` product packages."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from ..product.packages import load_product_package
from ..translator.freecad_translator import (
    translate_product_package_to_fcstd,
    translate_product_package_to_freecad_script,
)
from ..translator.freecad_translator.exporter import discover_freecad_executable
from ..translator.fusion360_translator import translate_product_package_to_fusion360_script
from ..translator.solidworks_translator import translate_product_package_to_solidworks_script
from .mjcf import export_product_package_to_mjcf
from .obj import export_product_package_to_obj
from .step import export_product_package_to_step
from .stl import export_product_package_to_stl


DEFAULT_FORMATS = ("step", "stl", "obj")
_SUFFIXES = {
    "step": ".step",
    "stl": ".stl",
    "obj": ".obj",
    "fcstd": ".FCStd",
    "mjcf": ".xml",
    "freecad-script": ".freecad.py",
    "fusion360-script": ".fusion360.py",
    "solidworks-script": ".solidworks.py",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simplecad-export",
        description="Export a validated .scadpkg product package.",
    )
    parser.add_argument("input", type=Path, help="input .scadpkg package")
    parser.add_argument(
        "--format",
        action="append",
        choices=tuple(_SUFFIXES),
        dest="formats",
        help="additional export format; may be repeated (default: step, stl, obj)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        action="append",
        default=[],
        metavar="FORMAT=PATH",
        help="override one output path; may be repeated",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true", help="validate and preflight without writing")
    parser.add_argument("--linear-deflection", type=float, default=0.1)
    parser.add_argument("--angular-deflection-degrees", type=float, default=20.0)
    parser.add_argument("--relative", action="store_true", help="use relative mesh deflection")
    parser.add_argument("--freecad-cmd", help="path to FreeCADCmd/FreeCAD for FCStd output")
    parser.add_argument("--document-name", default="SimpleCADProduct")
    return parser


def _parse_outputs(items: Sequence[str]) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for item in items:
        format_name, separator, raw_path = item.partition("=")
        if not separator or format_name not in _SUFFIXES or not raw_path:
            raise ValueError("--output must have the form FORMAT=PATH")
        if format_name in outputs:
            raise ValueError(f"duplicate --output for {format_name}")
        outputs[format_name] = Path(raw_path)
    return outputs


def _selected_formats(extra: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*DEFAULT_FORMATS, *(extra or ()))))


def _output_paths(input_path: Path, output_dir: Path, overrides: dict[str, Path], formats: Sequence[str]) -> dict[str, Path]:
    stem = input_path.name.removesuffix(".scadpkg")
    return {
        format_name: (overrides.get(format_name) or output_dir / f"{stem}{_SUFFIXES[format_name]}").expanduser().resolve()
        for format_name in formats
    }


def _freecad_command(value: str | None) -> str | None:
    if value is None:
        return discover_freecad_executable()
    path = Path(value).expanduser()
    return str(path.resolve()) if path.is_file() else shutil.which(value)


def _report_value(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _report_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_report_value(item) for item in value]
    return value


def run(argv: Sequence[str] | None = None) -> tuple[dict[str, Any], int]:
    args = _parser().parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if input_path.suffix.lower() != ".scadpkg":
        raise ValueError("input must end in .scadpkg")
    formats = _selected_formats(args.formats)
    overrides = _parse_outputs(args.output)
    unselected_overrides = sorted(set(overrides) - set(formats))
    if unselected_overrides:
        raise ValueError(
            "--output requires its format to be selected with --format: "
            + ", ".join(unselected_overrides)
        )
    output_paths = _output_paths(input_path, args.output_dir, overrides, formats)
    package = load_product_package(input_path)
    failures: dict[str, str] = {}
    checks: dict[str, dict[str, Any]] = {}
    freecad_cmd = _freecad_command(args.freecad_cmd) if "fcstd" in formats else None

    for format_name in formats:
        issues: list[str] = []
        if format_name == "fcstd" and freecad_cmd is None:
            issues.append("FreeCADCmd/FreeCAD not found; install it or pass --freecad-cmd")
        if format_name == "mjcf" and package.root_kind != "assembly":
            issues.append("MJCF export requires an assembly-rooted .scadpkg")
        if not args.check and not args.overwrite and output_paths[format_name].exists():
            issues.append("output already exists; pass --overwrite to replace it")
        checks[format_name] = {"output": str(output_paths[format_name]), "ok": not issues, "issues": issues}
        if issues:
            failures[format_name] = "; ".join(issues)

    report: dict[str, Any] = {
        "input": str(input_path),
        "root_kind": package.root_kind,
        "root_id": package.root_id,
        "check_only": bool(args.check),
        "formats": checks,
        "exports": {},
    }
    if args.check:
        report["ok"] = not failures
        return report, 0 if not failures else 1

    exporters: dict[str, Callable[[], Any]] = {
        "step": lambda: export_product_package_to_step(input_path, output_paths["step"]),
        "stl": lambda: export_product_package_to_stl(input_path, output_paths["stl"], linear_deflection=args.linear_deflection, angular_deflection_degrees=args.angular_deflection_degrees, relative=args.relative),
        "obj": lambda: export_product_package_to_obj(input_path, output_paths["obj"], linear_deflection=args.linear_deflection, angular_deflection_degrees=args.angular_deflection_degrees, relative=args.relative),
        "fcstd": lambda: translate_product_package_to_fcstd(input_path, str(output_paths["fcstd"]), document_name=args.document_name, freecad_cmd=freecad_cmd),
        "mjcf": lambda: export_product_package_to_mjcf(input_path, output_paths["mjcf"], linear_deflection=args.linear_deflection, angular_deflection_degrees=args.angular_deflection_degrees),
        "freecad-script": lambda: translate_product_package_to_freecad_script(input_path, document_name=args.document_name),
        "fusion360-script": lambda: translate_product_package_to_fusion360_script(input_path, document_name=args.document_name),
        "solidworks-script": lambda: translate_product_package_to_solidworks_script(input_path, document_name=args.document_name),
    }
    for format_name in formats:
        if format_name in failures:
            continue
        try:
            result = exporters[format_name]()
            if format_name.endswith("-script"):
                output_paths[format_name].parent.mkdir(parents=True, exist_ok=True)
                output_paths[format_name].write_text(str(result), encoding="utf-8")
                result = {"output_path": str(output_paths[format_name])}
            report["exports"][format_name] = {"ok": True, "report": _report_value(result)}
        except Exception as exc:  # retain independent exports when one target fails
            failures[format_name] = f"{type(exc).__name__}: {exc}"
            report["exports"][format_name] = {"ok": False, "error": failures[format_name]}
    report["ok"] = not failures
    if failures:
        report["failures"] = failures
    return report, 0 if not failures else 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report, exit_code = run(argv)
    except (OSError, PermissionError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, default=str, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
