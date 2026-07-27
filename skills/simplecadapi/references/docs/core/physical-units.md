# Physical Units And Dimension Inference

Declare physical meaning on variables:

```python
width = scad.var(
    "width",
    1.0,
    unit="in",
    tolerance=0.1,
    tolerance_unit="mm",
)
height = scad.var("height", 40.0, unit="mm", tolerance=0.2)
diagonal = scad.sqrt(width**2 + height**2)
```

## Canonical Rules

- Length, area, volume, and angle evaluate in `mm`, `mm^2`, `mm^3`, and `deg`.
- Declaration values remain available on `Var.default` and `Var.tolerance`.
- `tolerance_unit` defaults to `unit` and must have the same dimension.
- Bindings use the variable's declaration unit.
- Numeric constants are dimensionless coefficients; in addition/subtraction they
  are contextual offsets in the canonical result unit.

## Inference Rules

- Addition and subtraction require matching dimensions.
- Multiplication/division add/subtract dimension exponents.
- Constant integer powers multiply exponents.
- Square root requires every exponent to be even.
- `sin`, `cos`, and `tan` require Angle and return Dimensionless.
- `asin`, `acos`, and `atan` require Dimensionless and return Angle.
- `atan2` requires matching input dimensions and returns Angle.
- Unit-declared variables cannot mix with legacy variables without units.

Built-in symbols are `1`, `%`, `mm`, `cm`, `m`, `in`, `ft`, their square/cubic
forms, `deg`, and `rad`. Use `get_unit()`, `convert_value()`, and
`infer_dimension()` for explicit inspection.

Area and volume can be inferred and analyzed. Persisted manufacturing requirements
currently require a final Length or Angle result.

Read the source-checkout `docs/core/physical-units.md` for custom-unit JSON,
complete operation tables, failure conditions, and legacy behavior.
