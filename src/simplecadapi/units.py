"""Physical dimensions, engineering units, and expression inference."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, Dict, Mapping, Union


class UnitValidationError(ValueError):
    """Raised when units or expression dimensions are physically inconsistent."""


@dataclass(frozen=True)
class Dimension:
    """Physical dimension represented by integer length and angle exponents."""

    length: int = 0
    angle: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.length, bool) or not isinstance(self.length, int):
            raise TypeError("Dimension length exponent must be an integer")
        if isinstance(self.angle, bool) or not isinstance(self.angle, int):
            raise TypeError("Dimension angle exponent must be an integer")

    @property
    def name(self) -> str:
        names = {
            (0, 0): "Dimensionless",
            (1, 0): "Length",
            (2, 0): "Area",
            (3, 0): "Volume",
            (0, 1): "Angle",
        }
        return names.get((self.length, self.angle), self.symbol)

    @property
    def symbol(self) -> str:
        terms = []
        for symbol, exponent in (("L", self.length), ("A", self.angle)):
            if exponent == 0:
                continue
            terms.append(symbol if exponent == 1 else f"{symbol}^{exponent}")
        return "1" if not terms else " ".join(terms)

    @property
    def is_dimensionless(self) -> bool:
        return self == DIMENSIONLESS

    @property
    def is_design_dimension(self) -> bool:
        return self in {LENGTH, ANGLE}

    def multiply(self, other: "Dimension") -> "Dimension":
        return Dimension(self.length + other.length, self.angle + other.angle)

    def divide(self, other: "Dimension") -> "Dimension":
        return Dimension(self.length - other.length, self.angle - other.angle)

    def power(self, exponent: int) -> "Dimension":
        if isinstance(exponent, bool) or not isinstance(exponent, int):
            raise TypeError("Dimension exponent must be an integer")
        return Dimension(self.length * exponent, self.angle * exponent)

    def square_root(self) -> "Dimension":
        if self.length % 2 or self.angle % 2:
            raise UnitValidationError(
                f"Cannot take sqrt of {self.name}; every dimension exponent must be even"
            )
        return Dimension(self.length // 2, self.angle // 2)

    def to_dict(self) -> Dict[str, int]:
        return {"length": self.length, "angle": self.angle}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Dimension":
        if not isinstance(data, Mapping):
            raise TypeError("Dimension payload must be an object")
        if "length" not in data or "angle" not in data:
            raise ValueError("Dimension payload requires 'length' and 'angle'")
        return cls(length=data["length"], angle=data["angle"])


DIMENSIONLESS = Dimension()
LENGTH = Dimension(length=1)
AREA = Dimension(length=2)
VOLUME = Dimension(length=3)
ANGLE = Dimension(angle=1)


@dataclass(frozen=True)
class Unit:
    """Named unit with a scale to SimpleCAD's canonical numeric units.

    Custom units are supported and serialize their symbol, dimension, and scale.
    Registered built-in units serialize as compact symbols.
    """

    symbol: str
    dimension: Dimension
    scale_to_canonical: float

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("Unit symbol must be a non-empty string")
        if not isinstance(self.dimension, Dimension):
            raise TypeError("Unit dimension must be a Dimension")
        if (
            isinstance(self.scale_to_canonical, bool)
            or not isinstance(self.scale_to_canonical, Real)
        ):
            raise TypeError("Unit scale must be a real number")
        scale = float(self.scale_to_canonical)
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("Unit scale must be finite and greater than zero")
        object.__setattr__(self, "scale_to_canonical", scale)

    def to_canonical(self, value: int | float) -> float:
        number = _finite_number(value, label=f"Value in {self.symbol}")
        result = number * self.scale_to_canonical
        if not math.isfinite(result) or (number != 0.0 and result == 0.0):
            raise ValueError(f"Value in {self.symbol} is outside the supported range")
        return result

    def from_canonical(self, value: int | float) -> float:
        number = _finite_number(value, label="Canonical value")
        result = number / self.scale_to_canonical
        if not math.isfinite(result) or (number != 0.0 and result == 0.0):
            raise ValueError(
                f"Canonical value is outside the supported range for {self.symbol}"
            )
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "dimension": self.dimension.to_dict(),
            "scale_to_canonical": self.scale_to_canonical,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Unit":
        """Rebuild a custom unit from its serialized definition."""

        if not isinstance(data, Mapping):
            raise TypeError("Unit payload must be an object")
        required = {"symbol", "dimension", "scale_to_canonical"}
        missing = sorted(required.difference(data))
        if missing:
            raise ValueError(
                "Unit payload is missing required fields: " + ", ".join(missing)
            )
        return cls(
            symbol=data["symbol"],
            dimension=Dimension.from_dict(data["dimension"]),
            scale_to_canonical=data["scale_to_canonical"],
        )


UnitLike = Union[str, Unit]


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _unit(symbol: str, dimension: Dimension, scale: float) -> Unit:
    return Unit(symbol=symbol, dimension=dimension, scale_to_canonical=scale)


MM = _unit("mm", LENGTH, 1.0)
CM = _unit("cm", LENGTH, 10.0)
M = _unit("m", LENGTH, 1000.0)
INCH = _unit("in", LENGTH, 25.4)
FOOT = _unit("ft", LENGTH, 304.8)
DEGREE = _unit("deg", ANGLE, 1.0)
RADIAN = _unit("rad", ANGLE, 180.0 / math.pi)
ONE = _unit("1", DIMENSIONLESS, 1.0)
PERCENT = _unit("%", DIMENSIONLESS, 0.01)
SQUARE_MM = _unit("mm^2", AREA, 1.0)
SQUARE_CM = _unit("cm^2", AREA, 100.0)
SQUARE_M = _unit("m^2", AREA, 1_000_000.0)
SQUARE_INCH = _unit("in^2", AREA, 25.4**2)
SQUARE_FOOT = _unit("ft^2", AREA, 304.8**2)
CUBIC_MM = _unit("mm^3", VOLUME, 1.0)
CUBIC_CM = _unit("cm^3", VOLUME, 1000.0)
CUBIC_M = _unit("m^3", VOLUME, 1_000_000_000.0)
CUBIC_INCH = _unit("in^3", VOLUME, 25.4**3)
CUBIC_FOOT = _unit("ft^3", VOLUME, 304.8**3)


_UNIT_ALIASES: Dict[str, Unit] = {}


def _register(unit: Unit, *aliases: str) -> None:
    for token in (unit.symbol, *aliases):
        _UNIT_ALIASES[token.strip().lower()] = unit


_register(MM, "millimeter", "millimeters")
_register(CM, "centimeter", "centimeters")
_register(M, "meter", "meters")
_register(INCH, "inch", "inches")
_register(FOOT, "foot", "feet")
_register(RADIAN, "radian", "radians")
_register(DEGREE, "degree", "degrees", "°")
_register(ONE, "dimensionless")
_register(PERCENT, "percent")
_register(SQUARE_MM, "mm2")
_register(SQUARE_CM, "cm2")
_register(SQUARE_M, "m2")
_register(SQUARE_INCH, "in2", "square inch", "square inches")
_register(SQUARE_FOOT, "ft2", "square foot", "square feet")
_register(CUBIC_MM, "mm3")
_register(CUBIC_CM, "cm3", "ml")
_register(CUBIC_M, "m3")
_register(CUBIC_INCH, "in3", "cubic inch", "cubic inches")
_register(CUBIC_FOOT, "ft3", "cubic foot", "cubic feet")


def get_unit(value: UnitLike) -> Unit:
    """Resolve a built-in unit name/alias or return an existing ``Unit``."""

    if isinstance(value, Unit):
        return value
    if not isinstance(value, str) or not value.strip():
        raise TypeError("Unit must be a non-empty string or Unit")
    unit = _UNIT_ALIASES.get(value.strip().lower())
    if unit is None:
        supported = ", ".join(sorted({item.symbol for item in _UNIT_ALIASES.values()}))
        raise ValueError(f"Unknown unit '{value}'; supported units: {supported}")
    return unit


def unit_to_payload(unit: Unit) -> str | Dict[str, Any]:
    """Serialize a unit compactly without losing custom unit definitions."""

    if not isinstance(unit, Unit):
        raise TypeError("Unit payload serialization requires a Unit")
    registered = _UNIT_ALIASES.get(unit.symbol.strip().lower())
    return unit.symbol if registered == unit else unit.to_dict()


def unit_from_payload(value: Any) -> Unit:
    """Deserialize a registered unit symbol or a custom unit definition."""

    if isinstance(value, Mapping):
        return Unit.from_dict(value)
    return get_unit(value)


def canonical_unit_for_dimension(dimension: Dimension) -> Unit:
    """Return the canonical unit used by CAD and tolerance calculations.

    Length, area, volume, and angle use ``mm``, ``mm^2``, ``mm^3``, and ``deg``.
    """

    known = {
        DIMENSIONLESS: ONE,
        LENGTH: MM,
        AREA: SQUARE_MM,
        VOLUME: CUBIC_MM,
        ANGLE: DEGREE,
    }
    unit = known.get(dimension)
    if unit is not None:
        return unit
    return Unit(dimension.symbol, dimension, 1.0)


def convert_value(value: int | float, from_unit: UnitLike, to_unit: UnitLike) -> float:
    """Convert a finite numeric value between dimensionally compatible units."""

    source = get_unit(from_unit)
    target = get_unit(to_unit)
    if source.dimension != target.dimension:
        raise UnitValidationError(
            f"Cannot convert {source.dimension.name} unit '{source.symbol}' "
            f"to {target.dimension.name} unit '{target.symbol}'"
        )
    return target.from_canonical(source.to_canonical(value))


@dataclass(frozen=True)
class _Inference:
    dimension: Dimension | None
    typed: bool
    legacy: bool
    constant: bool


def _mixed_legacy_error(op: str) -> UnitValidationError:
    return UnitValidationError(
        f"Expression operation '{op}' mixes unit-declared variables with legacy "
        "variables that have no unit"
    )


def _require_no_mixed_legacy(op: str, *items: _Inference) -> None:
    if any(item.typed for item in items) and any(item.legacy for item in items):
        raise _mixed_legacy_error(op)


def _same_dimension(
    op: str, left: _Inference, right: _Inference
) -> Dimension | None:
    _require_no_mixed_legacy(op, left, right)
    if left.legacy or right.legacy:
        return None
    if left.constant and not left.typed:
        return right.dimension
    if right.constant and not right.typed:
        return left.dimension
    if left.dimension != right.dimension:
        left_name = left.dimension.name if left.dimension else "Unknown"
        right_name = right.dimension.name if right.dimension else "Unknown"
        raise UnitValidationError(
            f"Expression operation '{op}' requires matching dimensions; "
            f"got {left_name} and {right_name}"
        )
    return left.dimension


def _infer(
    node: "ScalarExpr",
    cache: Dict[int, _Inference],
    visiting: set[int],
) -> _Inference:
    from .expr import Const, Expr, Var

    node_id = id(node)
    cached = cache.get(node_id)
    if cached is not None:
        return cached
    if node_id in visiting:
        raise UnitValidationError(
            f"Expression graph contains a cycle at '{node.expr_id}'"
        )
    visiting.add(node_id)
    try:
        if isinstance(node, Const):
            result = _Inference(DIMENSIONLESS, False, False, True)
        elif isinstance(node, Var):
            result = (
                _Inference(node.unit.dimension, True, False, False)
                if node.unit is not None
                else _Inference(None, False, True, False)
            )
        elif isinstance(node, Expr):
            args = [_infer(arg, cache, visiting) for arg in node.args]
            typed = any(item.typed for item in args)
            legacy = any(item.legacy for item in args)
            constant = all(item.constant for item in args)
            if node.op in {"add", "sub"}:
                dimension = _same_dimension(node.op, args[0], args[1])
            elif node.op == "mul":
                _require_no_mixed_legacy(node.op, *args)
                dimension = (
                    None
                    if legacy
                    else args[0].dimension.multiply(args[1].dimension)  # type: ignore[union-attr]
                )
            elif node.op == "div":
                _require_no_mixed_legacy(node.op, *args)
                dimension = (
                    None
                    if legacy
                    else args[0].dimension.divide(args[1].dimension)  # type: ignore[union-attr]
                )
            elif node.op == "pow":
                _require_no_mixed_legacy(node.op, *args)
                if not typed:
                    dimension = None if legacy else DIMENSIONLESS
                else:
                    if args[1].legacy or args[1].dimension != DIMENSIONLESS:
                        raise UnitValidationError(
                            "A physical quantity exponent must be dimensionless"
                        )
                    if args[0].dimension == DIMENSIONLESS:
                        dimension = DIMENSIONLESS
                    else:
                        if not args[1].constant:
                            raise UnitValidationError(
                                "A dimensioned expression requires a constant numeric exponent"
                            )
                        exponent = float(node.args[1].evaluate())
                        if exponent.is_integer():
                            dimension = args[0].dimension.power(int(exponent))  # type: ignore[union-attr]
                        elif exponent == 0.5:
                            dimension = args[0].dimension.square_root()  # type: ignore[union-attr]
                        else:
                            raise UnitValidationError(
                                "Dimensioned powers currently support integer exponents or 0.5"
                            )
            elif node.op in {"neg", "abs"}:
                dimension = args[0].dimension
            elif node.op == "sqrt":
                dimension = (
                    None
                    if legacy
                    else args[0].dimension.square_root()  # type: ignore[union-attr]
                )
            elif node.op in {"sin", "cos", "tan"}:
                if typed and args[0].dimension != ANGLE:
                    raise UnitValidationError(
                        f"Expression operation '{node.op}' requires an Angle input"
                    )
                dimension = None if legacy else DIMENSIONLESS
            elif node.op in {"asin", "acos", "atan"}:
                if typed and args[0].dimension != DIMENSIONLESS:
                    raise UnitValidationError(
                        f"Expression operation '{node.op}' requires a Dimensionless input"
                    )
                dimension = ANGLE if typed else None
            elif node.op == "atan2":
                dimension = _same_dimension(node.op, args[0], args[1])
                if dimension is not None and typed:
                    dimension = ANGLE
                elif not typed:
                    dimension = None
            else:
                raise UnitValidationError(
                    f"Unsupported expression operation '{node.op}' for unit inference"
                )
            result = _Inference(dimension, typed, legacy, constant)
        else:
            raise TypeError(f"Unsupported expression node type: {type(node)!r}")
    finally:
        visiting.remove(node_id)
    cache[node_id] = result
    return result


def infer_dimension(value: "ScalarLike") -> Dimension | None:
    """Infer and validate an expression's result dimension.

    ``None`` means the expression uses only legacy variables without unit
    declarations. Expressions that contain explicit units are validated
    strictly and cannot mix in legacy variables.
    """

    from .expr import lift_scalar

    return _infer(lift_scalar(value), {}, set()).dimension


def expression_uses_units(value: "ScalarLike") -> bool:
    """Return whether an expression contains an explicit unit declaration."""

    from .expr import lift_scalar

    return _infer(lift_scalar(value), {}, set()).typed
