"""Command-line entry point for BREP inverse-engineering diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .agent_tools import (
    AGENT_TOOL_NAMES,
    BRepToolError,
    agent_tool_schemas,
    call_agent_tool,
)
from .compare import compare_steps
from .inspect import inspect_step
from .render import render_step_views
from .slices import SliceSpec, compare_step_slices


def _write_or_print(payload: Any, output: str | None) -> None:
    text = json.dumps(payload, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)


def _tool_arguments(value: str | None, path: str | None) -> Mapping[str, Any]:
    if path is not None:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = value or "{}"
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise BRepToolError("Tool arguments must encode one JSON object")
    return payload


def _slice_spec(value: str) -> SliceSpec:
    try:
        plane_text, coordinate_text = value.split(":", 1)
        plane = plane_text.lower()
        if plane not in {"xy", "xz", "yz"}:
            raise ValueError
        return SliceSpec(plane=plane, value=float(coordinate_text))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "slice must be PLANE:VALUE, for example xz:-1.6"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simplecad-brep",
        description="Inspect and compare STEP BREP geometry and topology.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect", help="Write a structured STEP BREP report"
    )
    inspect_parser.add_argument("step")
    inspect_parser.add_argument("--output", "-o")

    compare_parser = commands.add_parser(
        "compare", help="Run bidirectional geometry and topology checks"
    )
    compare_parser.add_argument("target")
    compare_parser.add_argument("candidate")
    compare_parser.add_argument("--output", "-o")
    compare_parser.add_argument("--geometric-tolerance", type=float, default=1.0e-7)
    compare_parser.add_argument("--volume-tolerance", type=float, default=1.0e-9)

    render_parser = commands.add_parser(
        "render", help="Render consistent orthographic and isometric views"
    )
    render_parser.add_argument("step")
    render_parser.add_argument("output")

    slices_parser = commands.add_parser(
        "slices", help="Compare sampled physical slices and render an XOR overlay"
    )
    slices_parser.add_argument("target")
    slices_parser.add_argument("candidate")
    slices_parser.add_argument("output")
    slices_parser.add_argument("--report")
    slices_parser.add_argument(
        "--slice",
        dest="slices",
        action="append",
        type=_slice_spec,
        help="Physical slice as PLANE:VALUE; repeat for multiple slices. Defaults to XYZ center slices.",
    )
    slices_parser.add_argument("--horizontal-samples", type=int, default=91)
    slices_parser.add_argument("--vertical-samples", type=int, default=121)

    commands.add_parser(
        "tools",
        help="Print framework-neutral Agent tool schemas",
    )

    tool_parser = commands.add_parser(
        "tool",
        help="Invoke one framework-neutral Agent tool with JSON arguments",
    )
    tool_parser.add_argument("name", choices=AGENT_TOOL_NAMES)
    arguments = tool_parser.add_mutually_exclusive_group()
    arguments.add_argument(
        "--arguments",
        help='Inline JSON object, for example \'{"model_path":"part.step"}\'',
    )
    arguments.add_argument(
        "--arguments-file",
        help="Path to a UTF-8 JSON object containing tool arguments",
    )
    tool_parser.add_argument("--output", "-o")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        report = inspect_step(args.step)
        _write_or_print(report.to_dict(), args.output)
        return 0
    if args.command == "compare":
        comparison = compare_steps(
            args.target,
            args.candidate,
            geometric_tolerance=args.geometric_tolerance,
            boolean_volume_tolerance=args.volume_tolerance,
        )
        _write_or_print(comparison.to_dict(), args.output)
        return 0 if comparison.hard_gate_passed else 1
    if args.command == "render":
        output = render_step_views(args.step, args.output)
        print(json.dumps({"output": str(output)}, indent=2))
        return 0
    if args.command == "slices":
        comparison = compare_step_slices(
            args.target,
            args.candidate,
            slices=args.slices,
            samples=(args.horizontal_samples, args.vertical_samples),
            output_path=args.output,
        )
        _write_or_print(comparison.to_dict(), args.report)
        return 0 if comparison.sampled_slices_identical else 1
    if args.command == "tools":
        _write_or_print(agent_tool_schemas(), None)
        return 0
    if args.command == "tool":
        result = call_agent_tool(
            args.name,
            _tool_arguments(args.arguments, args.arguments_file),
        )
        _write_or_print(result, args.output)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
