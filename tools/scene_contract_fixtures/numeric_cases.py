"""Numeric profile fixture vector construction."""

from __future__ import annotations

import struct

from simplecadapi.scene import (
    profile_cross,
    profile_f32_bits,
    profile_normalize,
)


def _f64_from_bits(value: str) -> float:
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _f64_bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def build_numeric_vectors() -> list[dict[str, object]]:
    vectors: list[dict[str, object]] = []
    for name, input_bits in (
        ("positive_zero", "0000000000000000"),
        ("negative_zero", "8000000000000000"),
        ("smallest_binary64_subnormal", "0000000000000001"),
        ("negative_smallest_binary64_subnormal", "8000000000000001"),
        ("binary32_smallest_subnormal", "36a0000000000000"),
        ("halfway_tie_to_even", "3ff0000010000000"),
        ("just_above_halfway", "3ff0000010000001"),
        ("binary32_largest_finite", "47efffffe0000000"),
    ):
        expected = profile_f32_bits(_f64_from_bits(input_bits))
        vectors.append(
            {
                "expected_bits": f"{expected:08x}",
                "input_bits": [input_bits],
                "name": name,
                "operation": "f32",
                "valid": True,
            }
        )
    for name, input_bits in (
        ("positive_overflow", "7fefffffffffffff"),
        ("negative_overflow", "ffefffffffffffff"),
        ("positive_infinity", "7ff0000000000000"),
        ("quiet_nan", "7ff8000000000000"),
    ):
        try:
            profile_f32_bits(_f64_from_bits(input_bits))
        except ValueError as exc:
            error = str(exc)
        else:
            raise AssertionError(name)
        vectors.append(
            {
                "error": error,
                "input_bits": [input_bits],
                "name": name,
                "operation": "f32",
                "valid": False,
            }
        )

    cross_inputs = (
        ("basis_cross", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        (
            "cancellation_cross",
            (134217729.0, 134217728.0, 0.0),
            (134217728.0, 134217727.0, 0.0),
        ),
    )
    for name, left, right in cross_inputs:
        result = profile_cross(left, right)
        vectors.append(
            {
                "expected_bits": [_f64_bits(component) for component in result],
                "input_bits": [
                    [_f64_bits(component) for component in left],
                    [_f64_bits(component) for component in right],
                ],
                "name": name,
                "operation": "cross",
                "valid": True,
            }
        )

    normalize_inputs = (
        ("normalize_3_4_0", (3.0, 4.0, -0.0)),
        ("normalize_equal_components", (1.0, 1.0, 1.0)),
    )
    for name, value in normalize_inputs:
        result = profile_normalize(value)
        vectors.append(
            {
                "expected_bits": [
                    f"{profile_f32_bits(component):08x}" for component in result
                ],
                "input_bits": [[_f64_bits(component) for component in value]],
                "name": name,
                "operation": "normalize",
                "valid": True,
            }
        )
    for name, value in (
        ("normalize_zero", (0.0, 0.0, 0.0)),
        (
            "normalize_overflow",
            (_f64_from_bits("7fefffffffffffff"), 1.0, 0.0),
        ),
    ):
        try:
            profile_normalize(value)
        except ValueError as exc:
            error = str(exc)
        else:
            raise AssertionError(name)
        vectors.append(
            {
                "error": error,
                "input_bits": [[_f64_bits(component) for component in value]],
                "name": name,
                "operation": "normalize",
                "valid": False,
            }
        )
    return vectors
