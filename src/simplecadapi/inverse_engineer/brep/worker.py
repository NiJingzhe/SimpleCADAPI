"""Trusted subprocess worker for bounded BREP evaluation stages.

Participant input isolation is enforced before this worker is invoked. Its
request paths are trusted evaluator inputs, not participant-controlled paths.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from simplecadapi.inspect import brep


def _execute(request: dict) -> dict:
    task = request["task"]
    target = request.get("target")
    current = request["current"]
    options = request.get("options", {})
    if task == "inspect":
        shape = brep.load_step_rshape(
            path=current,
            require_single_root=False,
            require_valid=False,
        )
        return brep.inspect_shape_rbrepinspection(
            shape=shape,
            source=current,
        ).to_dict()
    if task == "global":
        return brep.compare_global_properties_rdescriptor(
            target=target,
            current=current,
        )
    if task == "boundary":
        return brep.compare_boundary_distance_rdescriptor(
            target=target,
            current=current,
            **options,
        )
    if task == "material":
        return brep.compare_material_rdescriptor(
            target=target,
            current=current,
            **options,
        )
    if task == "section":
        return brep.compare_sections_rdescriptor(
            target=target,
            current=current,
            **options,
        )
    if task == "strict":
        target_shape = brep.load_step_rshape(
            path=target,
            require_single_root=False,
            require_valid=True,
        )
        current_shape = brep.load_step_rshape(
            path=current,
            require_single_root=False,
            require_valid=True,
        )
        return brep.compare_shapes_rbrepcomparison(
            target=target_shape,
            candidate=current_shape,
            target_name=target,
            candidate_name=current,
            **options,
        ).to_dict()
    raise ValueError(f"Unknown benchmark worker task: {task}")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        print("usage: worker REQUEST_JSON OUTPUT_JSON", file=sys.stderr)
        return 2
    request_path, output_path = map(Path, arguments)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = _execute(request)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
