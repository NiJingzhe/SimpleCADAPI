"""Semantic measurement identity and tolerance-aware display precision."""

from decimal import Decimal, InvalidOperation
from collections.abc import Mapping


def measurement_contract(measurement):
    """The observable being measured, independently of its geometry selection."""
    return {
        key: measurement.get(key)
        for key in (
            "kind",
            "definition",
            "direction",
            "point",
            "units",
            "coordinate_space",
        )
    }


def contract_errors(ledger, measurement):
    expected = ledger.get("measurement_contract")
    actual = measurement.get("measurement_contract")
    errors = []
    if not isinstance(expected, Mapping):
        return ["missing independent ledger measurement_contract"]
    if not isinstance(actual, Mapping) or actual != measurement_contract(measurement):
        return ["measurement_contract does not describe the measured observable"]
    for key in (
        "kind",
        "definition",
        "direction",
        "point",
        "units",
        "coordinate_space",
    ):
        if key not in expected or expected[key] != actual[key]:
            errors.append(f"measurement contract {key} differs from independent ledger")
    # If a verifier contract constrains the algorithm, it is also binding.
    if "method" in expected and expected["method"] != measurement.get("method"):
        errors.append("measurement contract method differs from independent ledger")
    return errors


def display_precision(value, decimals, ledger):
    """Check the actual formatter output, its rounding error and resolution.

    For a positive-width band, one display step must be no wider than the band
    and actual rounding error at most half its width. The displayed value must
    itself remain in the band. Zero-width bands require exact representation.
    These are expression checks; geometric acceptance still uses raw values.
    """
    errors = []
    if type(decimals) is not int or not 0 <= decimals <= 12:
        return {"status": "rejected", "errors": ["invalid display precision"]}
    try:
        value = float(value)
        text = f"{value:.{decimals}f}"
        raw, displayed = Decimal(str(value)), Decimal(text)
        lower, upper = Decimal(str(ledger["tolerance_min"])), Decimal(
            str(ledger["tolerance_max"])
        )
        if (
            not all(v.is_finite() for v in (raw, displayed, lower, upper))
            or lower > upper
        ):
            raise ValueError("nonfinite or invalid tolerance band")
        width = upper - lower
        error = abs(displayed - raw)
        step = Decimal(1).scaleb(-decimals)
        if width > 0 and step > width:
            errors.append("display precision step exceeds tolerance-band width")
        if error > width / 2:
            errors.append(
                "display precision rounding error exceeds half the tolerance-band width"
            )
        if not lower <= displayed <= upper:
            errors.append(
                "display precision rounds the value outside the tolerance band"
            )
        return {
            "status": "verified" if not errors else "rejected",
            "errors": errors,
            "display_text": text,
            "displayed_value": float(displayed),
            "rounding_error_mm": float(error),
            "display_step_mm": float(step),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        return {
            "status": "rejected",
            "errors": [f"invalid display precision contract: {exc}"],
        }
