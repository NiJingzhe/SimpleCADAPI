"""Declare, propagate, validate, and serialize a dimension tolerance chain.

Run from the repository root with:
    uv run python examples/04_dimension_tolerance_chain.py
"""

import json
from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")


@scad.model(graph_id="dimension_tolerance_chain")
def build_model():
    housing_span = scad.var(
        name="housing_span",
        default=100.0,
        unit="mm",
        tolerance=0.15,
        comment="Internal housing span",
    )
    bearing_width = scad.var(
        name="bearing_width",
        default=2.0,
        unit="cm",
        tolerance=(-0.04, 0.05),
        tolerance_unit="mm",
        comment="Bearing width",
    )
    spacer_width = scad.var(
        name="spacer_width",
        default=79.4,
        unit="mm",
        tolerance=0.05,
        comment="Spacer width",
    )
    axial_clearance = housing_span - bearing_width - spacer_width

    worst_case = scad.analyze_tolerance(
        value=axial_clearance,
        method="worst_case",
    )
    rss = scad.analyze_tolerance(value=axial_clearance, method="rss")

    housing = scad.make_box_rsolid(
        width=housing_span,
        height=10.0,
        depth=10.0,
        tag_prefix="tolerance_chain.housing",
        result_tag="part.tolerance_chain.housing",
    )
    session = scad.get_active_session()
    if session is None:
        raise RuntimeError("dimension tolerance model has no active session")
    session.require_tolerance(
        value=axial_clearance,
        tolerance=(-0.25, 0.24),
        tolerance_unit="mm",
        method="worst_case",
        name="axial_clearance",
    )
    report = session.validate_tolerances(raise_on_failure=True)
    scad.capture_result(value=housing)
    return {
        "housing": housing,
        "worst_case": worst_case,
        "rss": rss,
        "report": report,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = build_model()
    report_data = result.value
    (OUT / "dimension_tolerance_chain.model.json").write_text(
        result.model_json,
        encoding="utf-8",
    )

    worst_case = report_data["worst_case"]
    rss = report_data["rss"]
    print("housing_volume", round(report_data["housing"].get_volume(), 3))
    print(
        "worst_case",
        round(worst_case.nominal, 3),
        round(worst_case.lower_bound, 3),
        round(worst_case.upper_bound, 3),
    )
    print("result_unit", worst_case.dimension.name, worst_case.unit.symbol)
    print(
        "rss",
        round(rss.nominal, 3),
        round(rss.lower_bound, 3),
        round(rss.upper_bound, 3),
    )
    print("requirements_passed", report_data["report"].passed)
    print(
        "serialized_tolerance_graph",
        "tolerance_graph" in json.loads(result.model_json),
    )


if __name__ == "__main__":
    main()
