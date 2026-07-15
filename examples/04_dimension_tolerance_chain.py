"""Declare, propagate, validate, and serialize a dimension tolerance chain.

Run from the repository root with:
    uv run python examples/04_dimension_tolerance_chain.py
"""

import json
from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)

housing_span = scad.var(
    "housing_span",
    100.0,
    unit="mm",
    tolerance=0.15,
    comment="Internal housing span",
)
bearing_width = scad.var(
    "bearing_width",
    2.0,
    unit="cm",
    tolerance=(-0.04, 0.05),
    tolerance_unit="mm",
    comment="Bearing width",
)
spacer_width = scad.var(
    "spacer_width",
    79.4,
    unit="mm",
    tolerance=0.05,
    comment="Spacer width",
)
axial_clearance = housing_span - bearing_width - spacer_width

worst_case = scad.analyze_tolerance(axial_clearance, method="worst_case")
rss = scad.analyze_tolerance(axial_clearance, method="rss")

with scad.GraphSession() as session:
    housing = scad.make_box_rsolid(housing_span, 10.0, 10.0)
    session.require_tolerance(
        axial_clearance,
        (-0.25, 0.24),
        tolerance_unit="mm",
        method="worst_case",
        name="axial_clearance",
    )

report = session.validate_tolerances(raise_on_failure=True)
model_json = scad.export_model_json(session)
(OUT / "dimension_tolerance_chain.model.json").write_text(
    model_json, encoding="utf-8"
)

print("housing_volume", round(housing.get_volume(), 3))
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
print("requirements_passed", report.passed)
print("serialized_tolerance_graph", "tolerance_graph" in json.loads(model_json))
