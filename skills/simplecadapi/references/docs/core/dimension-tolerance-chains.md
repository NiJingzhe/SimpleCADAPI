# Dimension Tolerance Chains

SimpleCADAPI can attach manufacturing tolerances to declared dimension variables, propagate them through the expression DAG, and verify derived dimensions against design requirements.

This feature is separate from sketch-solver residual tolerances, boolean fuzzy tolerances, mesh resolution, and geometric fitting tolerances.

## Core Workflow

```python
import simplecadapi as scad

housing = scad.var("housing", 100.0, unit="mm", tolerance=0.15)
bearing = scad.var("bearing", 2.0, unit="cm", tolerance=(-0.04, 0.05), tolerance_unit="mm")
spacer = scad.var("spacer", 79.4, unit="mm", tolerance=0.05)
clearance = housing - bearing - spacer

worst_case = scad.analyze_tolerance(clearance, method="worst_case")
rss = scad.analyze_tolerance(clearance, method="rss")

with scad.GraphSession() as session:
    body = scad.make_box_rsolid(housing, 10.0, 10.0)
    session.require_tolerance(
        clearance,
        (-0.25, 0.24),
        method="worst_case",
        name="axial_clearance",
        tolerance_unit="mm",
    )

report = session.validate_tolerances(raise_on_failure=True)
model_json = scad.export_model_json(session)
```

## Rules

- A scalar tolerance is symmetric: `0.1` means `-0.1/+0.1`.
- A two-value sequence contains signed `(lower_deviation, upper_deviation)` values.
- Every variable in a tolerance chain must declare a finite tolerance.
- `tolerance_unit` defaults to `unit`; different nominal/tolerance units must
  have the same dimension.
- Length and angle propagate in canonical `mm` and `deg` units.
- Expression dimensions are inferred and validated before propagation.
- Area and volume can be analyzed, while requirements currently accept final
  Length and Angle results only.
- Tolerance sources are identified by `expr_id`, not by variable name.
- `worst_case` uses exact dependency-aware affine propagation and conservative nonlinear interval propagation.
- `rss` uses analytic first-order sensitivities, assumes distinct variables are independent, and combines repeated occurrences of the same variable before RSS.
- Both methods reject a chain that is undefined anywhere inside its declared source intervals.
- Export, import, replay, and FreeCAD translation validate stored requirements automatically.
- Legacy model JSON without `tolerance_graph` imports with an empty graph.
- Nominal replay continues to use numeric operation snapshots; tolerance analysis does not regenerate worst-case geometry.
- Import recomputes dimensions and rejects tampered unit or target-dimension data.

Use `check_tolerance()` for a standalone non-raising check. Use `GraphSession.require_tolerance()` when the requirement must be serialized and enforced.

See the source-checkout guide at `docs/core/dimension-tolerance-chains.md` for propagation details, failure conditions, JSON shapes, and FreeCAD behavior.
