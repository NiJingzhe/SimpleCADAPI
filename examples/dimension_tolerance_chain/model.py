"""Declare, propagate, validate, and serialize a dimension tolerance chain.

Run from the repository root with:
    uv run python examples/dimension_tolerance_chain/model.py
"""

import json
from pathlib import Path

import simplecadapi as scad


OUT = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT / "dimension_tolerance_chain.scadpkg"
STEP_PATH = OUT / "dimension_tolerance_chain.step"
FCSTD_PATH = OUT / "dimension_tolerance_chain.FCStd"


@scad.part(
    id="dimension_tolerance_chain",
    revision="1.0.0",
    cache="off",
    project_root=Path(__file__).resolve().parents[2],
)
def build_dimension_tolerance_chain_part() -> scad.Part:
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
    scad.analyze_tolerance(value=axial_clearance, method="worst_case")
    scad.analyze_tolerance(value=axial_clearance, method="rss")
    housing = scad.make_box_rsolid(
        width=housing_span,
        height=10.0,
        depth=10.0,
        tag_prefix="tolerance_chain.housing",
        result_tag="part.tolerance_chain.housing",
    )
    session = scad.get_active_session()
    if session is None:
        raise RuntimeError("dimension tolerance builder requires an active session")
    session.require_tolerance(
        value=axial_clearance,
        tolerance=(-0.25, 0.24),
        tolerance_unit="mm",
        method="worst_case",
        name="axial_clearance",
    )
    session.validate_tolerances(raise_on_failure=True)
    return scad.make_part_rpart(
        part_id="dimension_tolerance_chain",
        body=housing,
        name="Dimension tolerance chain housing",
    )


def build_model():
    result = build_dimension_tolerance_chain_part()
    session = result.feature_graph.restore_session()
    requirement = session.tolerance_graph.requirements[0]
    expression = session.expression_graph.get(requirement.target_expr_id)
    if expression is None:
        raise RuntimeError("tolerance target expression was not restored")
    worst_case = scad.analyze_tolerance(value=expression, method="worst_case")
    rss = scad.analyze_tolerance(value=expression, method="rss")
    data = {
        "housing": result.part,
        "worst_case": worst_case,
        "rss": rss,
        "report": session.validate_tolerances(raise_on_failure=True),
    }
    return (
        data,
        scad.export_model_json(session),
        scad.export_session_json(session),
        result,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report_data, model_json, session_json, result = build_model()
    (OUT / "dimension_tolerance_chain.model.json").write_text(
        model_json,
        encoding="utf-8",
    )
    (OUT / "dimension_tolerance_chain.session.json").write_text(
        session_json,
        encoding="utf-8",
    )
    package_path = OUT / "dimension_tolerance_chain.scadpkg"
    scad.capture(result, package_path)
    step_report = scad.exporter.export_product_package_to_step(package_path, STEP_PATH)
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(FCSTD_PATH),
        document_name="DimensionToleranceChain",
    )

    worst_case = report_data["worst_case"]
    rss = report_data["rss"]
    print("housing_volume", round(report_data["housing"].body.get_volume(), 3))
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
    print("serialized_tolerance_graph", "tolerance_graph" in json.loads(model_json))
    print("product_package", package_path)
    print("ap242_step", step_report.output_path)
    print("fcstd", FCSTD_PATH)


if __name__ == "__main__":
    main()
