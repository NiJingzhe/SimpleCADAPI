"""Complete coverage for expression-driven dimension tolerance chains."""

from __future__ import annotations

import json
import math
import unittest

import simplecadapi as scad


class TestDimensionToleranceDeclaration(unittest.TestCase):
    def test_symmetric_and_asymmetric_tolerances(self):
        symmetric = scad.var("width", 10.0, tolerance=0.2)
        asymmetric = scad.var("shaft", 8.0, tolerance=(-0.05, 0.0))

        self.assertEqual(symmetric.tolerance.lower_deviation, -0.2)
        self.assertEqual(symmetric.tolerance.upper_deviation, 0.2)
        self.assertEqual(asymmetric.tolerance.lower_deviation, -0.05)
        self.assertEqual(asymmetric.tolerance.upper_deviation, 0.0)

    def test_dimension_tolerance_roundtrip(self):
        tolerance = scad.DimensionTolerance(-0.1, 0.3)
        self.assertEqual(
            scad.DimensionTolerance.from_dict(tolerance.to_dict()), tolerance
        )
        self.assertAlmostEqual(tolerance.width, 0.4)

    def test_invalid_variable_and_tolerance_values_are_rejected(self):
        invalid_calls = [
            lambda: scad.var("x", True),
            lambda: scad.var("x", math.inf),
            lambda: scad.var("x", 1.0, tolerance=True),
            lambda: scad.var("x", 1.0, tolerance=-0.1),
            lambda: scad.var("x", 1.0, tolerance=(0.1, 0.2)),
            lambda: scad.var("x", 1.0, tolerance=(-0.2, -0.1)),
            lambda: scad.var("x", 1.0, tolerance=(-0.1, 0.1, 0.2)),
            lambda: scad.DimensionTolerance(float("nan"), 0.1),
        ]

        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises((TypeError, ValueError)):
                call()

    def test_expression_graph_preserves_variable_tolerances_and_forward_refs(self):
        width = scad.var("width", 10.0, tolerance=(-0.1, 0.2))
        graph = scad.ExpressionGraph()
        expression = width * 2.0
        graph.register(expression)
        payload = graph.to_dict()
        payload["nodes"].reverse()

        rebuilt = scad.ExpressionGraph.from_dict(payload)
        rebuilt_width = rebuilt.get(width.expr_id)

        self.assertIsInstance(rebuilt_width, scad.Var)
        self.assertEqual(rebuilt_width.tolerance, width.tolerance)
        self.assertAlmostEqual(rebuilt.get(expression.expr_id).evaluate(), 20.0)

    def test_var_positional_expr_id_remains_compatible(self):
        variable = scad.Var("width", 10.0, "plate width", "var_width")

        self.assertEqual(variable.expr_id, "var_width")
        self.assertIsNone(variable.tolerance)

    def test_malformed_expression_graphs_are_rejected(self):
        valid_var = {
            "expr_id": "var_x",
            "kind": "var",
            "name": "x",
            "default": 1.0,
            "tolerance": {"lower_deviation": -0.1, "upper_deviation": 0.1},
        }
        payloads = [
            {"nodes": [valid_var, dict(valid_var)]},
            {
                "nodes": [
                    {
                        "expr_id": "expr_a",
                        "kind": "expr",
                        "op": "neg",
                        "args": ["missing"],
                    }
                ]
            },
            {
                "nodes": [
                    {
                        "expr_id": "expr_a",
                        "kind": "expr",
                        "op": "neg",
                        "args": ["expr_b"],
                    },
                    {
                        "expr_id": "expr_b",
                        "kind": "expr",
                        "op": "neg",
                        "args": ["expr_a"],
                    },
                ]
            },
            {
                "nodes": [
                    valid_var,
                    {
                        "expr_id": "expr_bad",
                        "kind": "expr",
                        "op": "add",
                        "args": ["var_x"],
                    },
                ]
            },
        ]

        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                scad.ExpressionGraph.from_dict(payload)

    def test_expression_registration_is_atomic_for_conflicting_ids(self):
        left = scad.Var(
            "left",
            1.0,
            expr_id="var_duplicate",
            tolerance=scad.DimensionTolerance.symmetric(0.1),
        )
        right = scad.Var(
            "right",
            2.0,
            expr_id="var_duplicate",
            tolerance=scad.DimensionTolerance.symmetric(0.1),
        )
        expression = scad.Expr("add", (left, right))
        graph = scad.ExpressionGraph()

        with self.assertRaisesRegex(ValueError, "already registered"):
            graph.register(expression)

        self.assertEqual(graph.node_count, 0)

    def test_expression_registration_rejects_cycles_without_mutation(self):
        expression = scad.Expr("neg", (scad.const(1.0),), expr_id="expr_cycle")
        object.__setattr__(expression, "args", (expression,))
        graph = scad.ExpressionGraph()

        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.register(expression)

        self.assertEqual(graph.node_count, 0)

    def test_expression_arguments_are_normalized_to_an_immutable_tuple(self):
        arguments = [scad.const(1.0)]
        expression = scad.Expr("neg", arguments)
        arguments[0] = expression

        self.assertIsInstance(expression.args, tuple)
        self.assertIsNot(expression.args[0], expression)

    def test_signed_zero_nodes_with_the_same_id_are_distinct(self):
        positive = scad.Const(0.0, expr_id="const_zero")
        negative = scad.Const(-0.0, expr_id="const_zero")
        graph = scad.ExpressionGraph()
        graph.register(positive)

        with self.assertRaisesRegex(ValueError, "different node"):
            graph.register(negative)

    def test_expression_payload_missing_required_fields_is_rejected_cleanly(self):
        payloads = [
            {"nodes": [{"expr_id": "const_x", "kind": "const"}]},
            {
                "nodes": [
                    {"expr_id": "var_x", "kind": "var", "default": 1.0}
                ]
            },
            {
                "nodes": [
                    {"expr_id": "var_x", "kind": "var", "name": "x"}
                ]
            },
            {
                "nodes": [
                    {"expr_id": "expr_x", "kind": "expr", "args": []}
                ]
            },
        ]

        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                scad.ExpressionGraph.from_dict(payload)

    def test_huge_numeric_inputs_are_rejected_as_non_finite(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            scad.const(10**10000)


class TestWorstCaseTolerancePropagation(unittest.TestCase):
    def test_addition_and_subtraction_preserve_asymmetric_deviations(self):
        a = scad.var("a", 10.0, tolerance=(-0.1, 0.2))
        b = scad.var("b", 5.0, tolerance=(-0.3, 0.4))

        result = scad.analyze_tolerance(a - b)

        self.assertAlmostEqual(result.nominal, 5.0)
        self.assertAlmostEqual(result.lower_deviation, -0.5)
        self.assertAlmostEqual(result.upper_deviation, 0.5)
        self.assertEqual(len(result.contributions), 2)

    def test_linear_scaling_and_repeated_variable_dependency_are_exact(self):
        x = scad.var("x", 4.0, tolerance=(-0.2, 0.3))

        scaled = scad.analyze_tolerance(-2.0 * x + 1.0)
        cancelled = scad.analyze_tolerance(x - x)

        self.assertAlmostEqual(scaled.lower_deviation, -0.6)
        self.assertAlmostEqual(scaled.upper_deviation, 0.4)
        self.assertAlmostEqual(cancelled.lower_deviation, 0.0)
        self.assertAlmostEqual(cancelled.upper_deviation, 0.0)

    def test_multiplication_handles_all_interval_corner_signs(self):
        a = scad.var("a", -1.0, tolerance=(-1.0, 0.5))
        b = scad.var("b", 3.0, tolerance=(-1.0, 1.0))

        result = scad.analyze_tolerance(a * b)

        self.assertAlmostEqual(result.nominal, -3.0)
        self.assertAlmostEqual(result.lower_bound, -8.0)
        self.assertAlmostEqual(result.upper_bound, -1.0)

    def test_division_rejects_denominator_interval_containing_zero(self):
        numerator = scad.var("numerator", 2.0, tolerance=0.1)
        denominator = scad.var("denominator", 1.0, tolerance=1.0)

        with self.assertRaisesRegex(
            scad.ToleranceAnalysisError, "denominator.*contains zero"
        ):
            scad.analyze_tolerance(numerator / denominator)

    def test_integer_and_fractional_power_intervals(self):
        signed = scad.var("signed", 0.0, tolerance=2.0)
        positive = scad.var("positive", 4.0, tolerance=(-3.0, 5.0))

        squared = scad.analyze_tolerance(signed**2)
        rooted = scad.analyze_tolerance(scad.sqrt(positive))

        self.assertLessEqual(squared.lower_bound, 0.0)
        self.assertGreaterEqual(squared.upper_bound, 4.0)
        self.assertAlmostEqual(squared.upper_bound, 4.0)
        self.assertLessEqual(rooted.lower_bound, 1.0)
        self.assertGreaterEqual(rooted.upper_bound, 3.0)
        self.assertAlmostEqual(rooted.lower_bound, 1.0)
        self.assertAlmostEqual(rooted.upper_bound, 3.0)

    def test_power_domain_errors_are_explicit(self):
        negative = scad.var("negative", -2.0, tolerance=0.1)
        crosses_zero = scad.var("crosses_zero", 0.0, tolerance=0.1)

        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "negative base"):
            scad.analyze_tolerance(negative**0.5)
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "zero"):
            scad.analyze_tolerance(crosses_zero ** -1)

    def test_invalid_constant_subexpressions_use_analysis_errors(self):
        expression = scad.sqrt(-1.0)

        with self.assertRaisesRegex(
            scad.ToleranceAnalysisError, "declared tolerance interval"
        ):
            scad.analyze_tolerance(expression)

    def test_trigonometric_extrema_and_discontinuities(self):
        angle = scad.var("angle", 0.0, tolerance=(-math.pi, math.pi))
        tangent_angle = scad.var(
            "tangent_angle", math.pi / 2.0, tolerance=0.1
        )

        sine = scad.analyze_tolerance(scad.sin(angle))
        cosine = scad.analyze_tolerance(scad.cos(angle))

        self.assertEqual((sine.lower_bound, sine.upper_bound), (-1.0, 1.0))
        self.assertEqual((cosine.lower_bound, cosine.upper_bound), (-1.0, 1.0))
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "discontinuity"):
            scad.analyze_tolerance(scad.tan(tangent_angle))

    def test_inverse_function_domains_are_checked_over_full_interval(self):
        below_sqrt = scad.var("below_sqrt", 0.1, tolerance=0.2)
        outside_unit = scad.var("outside_unit", 0.9, tolerance=0.2)

        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "below zero"):
            scad.analyze_tolerance(scad.sqrt(below_sqrt))
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "outside"):
            scad.analyze_tolerance(scad.asin(outside_unit))
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "outside"):
            scad.analyze_tolerance(scad.acos(outside_unit))

    def test_atan_and_atan2_propagation(self):
        y = scad.var("y", 2.0, tolerance=0.1)
        x = scad.var("x", 3.0, tolerance=0.2)
        origin_y = scad.var("origin_y", 0.0, tolerance=0.1)
        origin_x = scad.var("origin_x", 0.0, tolerance=0.1)

        atan_result = scad.analyze_tolerance(scad.atan(y))
        atan2_result = scad.analyze_tolerance(scad.atan2(y, x))

        self.assertLess(atan_result.lower_bound, atan_result.upper_bound)
        self.assertLess(atan2_result.lower_bound, atan2_result.upper_bound)
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "undefined origin"):
            scad.analyze_tolerance(scad.atan2(origin_y, origin_x))

    def test_atan2_negative_x_branch_cut_is_not_underestimated(self):
        y = scad.var("y", 0.0, tolerance=0.1)
        x = scad.var("x", -2.0, tolerance=0.1)
        expression = scad.atan2(y, x)

        result = scad.analyze_tolerance(expression)

        self.assertEqual(result.lower_bound, -math.pi)
        self.assertEqual(result.upper_bound, math.pi)
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "branch cut"):
            scad.analyze_tolerance(expression, method="rss")

    def test_atan2_signed_zero_branch_cut_is_rejected_for_rss(self):
        y = scad.var("y", -0.0, tolerance=(0.0, 0.1))
        x = scad.var("x", -2.0, tolerance=0.0)
        expression = scad.atan2(y, x)

        worst_case = scad.analyze_tolerance(expression)

        self.assertEqual(worst_case.lower_bound, -math.pi)
        self.assertEqual(worst_case.upper_bound, math.pi)
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "branch cut"):
            scad.analyze_tolerance(expression, method="rss")

    def test_abs_crossing_zero_and_negation(self):
        value = scad.var("value", 0.25, tolerance=0.5)

        absolute = scad.analyze_tolerance(abs(value))
        negated = scad.analyze_tolerance(-value)

        self.assertEqual(absolute.lower_bound, 0.0)
        self.assertAlmostEqual(absolute.upper_bound, 0.75)
        self.assertAlmostEqual(negated.lower_deviation, -0.5)
        self.assertAlmostEqual(negated.upper_deviation, 0.5)

    def test_nonlinear_contributions_are_reported_in_target_units(self):
        value = scad.var("value", 2.0, tolerance=0.1)

        result = scad.analyze_tolerance(value**2)

        self.assertIsNone(result.contributions[0].sensitivity)
        self.assertAlmostEqual(result.contributions[0].lower_deviation, -0.39)
        self.assertAlmostEqual(result.contributions[0].upper_deviation, 0.41)

    def test_large_nominal_value_does_not_erase_small_declared_deviations(self):
        value = scad.var("large", 1e16, tolerance=0.1)

        result = scad.analyze_tolerance(value)

        self.assertEqual(result.lower_deviation, -0.1)
        self.assertEqual(result.upper_deviation, 0.1)
        self.assertLess(result.lower_bound, result.nominal)
        self.assertGreater(result.upper_bound, result.nominal)

    def test_underflowed_nonlinear_range_remains_conservative(self):
        value = scad.var("tiny", 0.0, tolerance=1e-200)

        result = scad.analyze_tolerance(value**2)
        check = scad.check_tolerance(value**2, 0.0)

        self.assertEqual(result.lower_deviation, 0.0)
        self.assertGreater(result.upper_deviation, 0.0)
        self.assertFalse(check.passed)

    def test_large_atan_input_keeps_nonzero_worst_case_range(self):
        value = scad.var("large", 1e160, tolerance=1e100)

        result = scad.analyze_tolerance(scad.atan(value))

        self.assertLess(result.lower_deviation, 0.0)
        self.assertGreater(result.upper_deviation, 0.0)

    def test_zero_tolerance_large_periodic_input_remains_a_point(self):
        angle = scad.var("angle", 1e16, tolerance=0.0)

        tangent = scad.analyze_tolerance(scad.tan(angle))
        sine = scad.analyze_tolerance(scad.sin(angle))

        self.assertEqual(tangent.lower_deviation, 0.0)
        self.assertEqual(tangent.upper_deviation, 0.0)
        self.assertEqual(sine.lower_deviation, 0.0)
        self.assertEqual(sine.upper_deviation, 0.0)

    def test_exact_zero_absolute_value_is_not_spuriously_widened(self):
        value = scad.var("zero", 0.0, tolerance=0.0)

        result = scad.analyze_tolerance(abs(value))

        self.assertEqual(result.lower_deviation, 0.0)
        self.assertEqual(result.upper_deviation, 0.0)


class TestRssTolerancePropagation(unittest.TestCase):
    def test_independent_sources_are_combined_by_root_sum_square(self):
        a = scad.var("a", 10.0, tolerance=0.3)
        b = scad.var("b", 4.0, tolerance=0.4)

        result = scad.analyze_tolerance(a + b, method="rss")

        self.assertAlmostEqual(result.lower_deviation, -0.5)
        self.assertAlmostEqual(result.upper_deviation, 0.5)

    def test_repeated_source_is_not_treated_as_independent(self):
        x = scad.var("x", 2.0, tolerance=0.2)

        cancelled = scad.analyze_tolerance(x - x, method="rss")
        doubled = scad.analyze_tolerance(x + x, method="rss")

        self.assertAlmostEqual(cancelled.lower_deviation, 0.0)
        self.assertAlmostEqual(cancelled.upper_deviation, 0.0)
        self.assertAlmostEqual(doubled.lower_deviation, -0.4)
        self.assertAlmostEqual(doubled.upper_deviation, 0.4)

    def test_nonlinear_sensitivity_is_analytic(self):
        x = scad.var("x", 2.0, tolerance=0.1)

        squared = scad.analyze_tolerance(x**2, method="rss")
        sine = scad.analyze_tolerance(scad.sin(x), method="rss")

        self.assertAlmostEqual(squared.lower_deviation, -0.4)
        self.assertAlmostEqual(squared.upper_deviation, 0.4)
        self.assertAlmostEqual(
            sine.upper_deviation, abs(math.cos(2.0)) * 0.1
        )

    def test_rss_rejects_non_differentiable_and_invalid_intervals(self):
        at_zero = scad.var("at_zero", 0.0, tolerance=0.1)
        denominator = scad.var("denominator", 1.0, tolerance=1.0)
        numerator = scad.var("numerator", 2.0, tolerance=0.1)

        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "abs"):
            scad.analyze_tolerance(abs(at_zero), method="rss")
        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "denominator"):
            scad.analyze_tolerance(numerator / denominator, method="rss")

    def test_all_unary_and_binary_derivative_paths_are_supported(self):
        a = scad.var("a", 0.5, tolerance=0.01)
        b = scad.var("b", 2.0, tolerance=0.02)
        expressions = [
            a + b,
            a - b,
            a * b,
            a / b,
            b**a,
            -a,
            abs(a),
            scad.sin(a),
            scad.cos(a),
            scad.tan(a),
            scad.sqrt(b),
            scad.acos(a),
            scad.asin(a),
            scad.atan(a),
            scad.atan2(a, b),
        ]

        for expression in expressions:
            with self.subTest(op=getattr(expression, "op", None)):
                result = scad.analyze_tolerance(expression, method="rss")
                self.assertTrue(math.isfinite(result.lower_bound))
                self.assertTrue(math.isfinite(result.upper_bound))

    def test_constant_boundary_functions_have_zero_rss_tolerance(self):
        expressions = [scad.sqrt(0.0), scad.acos(1.0), scad.asin(-1.0)]

        for expression in expressions:
            with self.subTest(op=expression.op):
                result = scad.analyze_tolerance(expression, method="rss")
                self.assertEqual(result.lower_deviation, 0.0)
                self.assertEqual(result.upper_deviation, 0.0)

    def test_rss_uses_overflow_safe_root_sum_square(self):
        a = scad.var("a", 0.0, tolerance=1e200)
        b = scad.var("b", 0.0, tolerance=1e200)

        result = scad.analyze_tolerance(a + b, method="rss")

        expected = math.hypot(1e200, 1e200)
        self.assertTrue(math.isfinite(result.upper_deviation))
        self.assertLessEqual(result.lower_deviation, -expected)
        self.assertGreaterEqual(result.upper_deviation, expected)
        self.assertAlmostEqual(result.upper_deviation / expected, 1.0)

    def test_rss_atan2_derivative_is_stable_for_large_coordinates(self):
        y = scad.var("y", 1e200, tolerance=1e190)
        x = scad.var("x", 1e200, tolerance=1e190)

        result = scad.analyze_tolerance(scad.atan2(y, x), method="rss")

        self.assertTrue(math.isfinite(result.upper_deviation))
        self.assertGreater(result.upper_deviation, 0.0)

    def test_rss_atan_derivative_does_not_underflow_before_contribution(self):
        value = scad.var("large", 1e160, tolerance=1e100)

        result = scad.analyze_tolerance(scad.atan(value), method="rss")

        self.assertGreaterEqual(result.upper_deviation, 1e-220)

    def test_ill_conditioned_affine_coefficients_preserve_source_effect(self):
        value = scad.var("value", 1.0, tolerance=0.1)
        expression = (1e16 * value + value) - 1e16 * value

        worst_case = scad.analyze_tolerance(expression)
        rss = scad.analyze_tolerance(expression, method="rss")

        self.assertLessEqual(worst_case.lower_deviation, -0.1)
        self.assertGreaterEqual(worst_case.upper_deviation, 0.1)
        self.assertLessEqual(rss.lower_deviation, -0.1)
        self.assertGreaterEqual(rss.upper_deviation, 0.1)


class TestToleranceRequirementsAndPersistence(unittest.TestCase):
    def test_check_tolerance_returns_margins_without_raising(self):
        a = scad.var("a", 10.0, tolerance=0.2)
        b = scad.var("b", 5.0, tolerance=0.1)

        passing = scad.check_tolerance(a - b, 0.3, name="clearance")
        failing = scad.check_tolerance(a - b, 0.2, name="clearance")

        self.assertTrue(passing.passed)
        self.assertAlmostEqual(passing.lower_margin, 0.0)
        self.assertAlmostEqual(passing.upper_margin, 0.0)
        self.assertFalse(failing.passed)

    def test_requirement_comparison_does_not_scale_epsilon_by_nominal(self):
        value = scad.var("large", 1e16, tolerance=0.1)

        check = scad.check_tolerance(value, 0.0)

        self.assertFalse(check.passed)
        self.assertLess(check.lower_margin, 0.0)
        self.assertLess(check.upper_margin, 0.0)

    def test_analysis_rejects_conflicting_expression_ids_before_caching(self):
        left = scad.Var(
            "left",
            1.0,
            expr_id="var_duplicate",
            tolerance=scad.DimensionTolerance.symmetric(0.1),
        )
        right = scad.Var(
            "right",
            2.0,
            expr_id="var_duplicate",
            tolerance=scad.DimensionTolerance.symmetric(0.2),
        )

        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "multiple"):
            scad.analyze_tolerance(scad.Expr("add", (left, right)))

    def test_every_variable_requires_an_explicit_source_tolerance(self):
        declared = scad.var("declared", 2.0, tolerance=0.1)
        missing = scad.var("missing", 1.0)

        with self.assertRaisesRegex(scad.ToleranceAnalysisError, "missing"):
            scad.analyze_tolerance(declared + missing)

    def test_tolerance_graph_validates_all_requirements(self):
        a = scad.var("a", 10.0, tolerance=0.2)
        b = scad.var("b", 5.0, tolerance=0.1)
        expression_graph = scad.ExpressionGraph()
        tolerance_graph = scad.ToleranceGraph(expression_graph)
        tolerance_graph.require(a + b, 0.3, name="overall")
        tolerance_graph.require(a - b, 0.2, name="clearance")

        report = tolerance_graph.validate()

        self.assertFalse(report.passed)
        self.assertEqual(report.checks[0].requirement.name, "overall")
        with self.assertRaises(scad.ToleranceValidationError) as context:
            tolerance_graph.validate(raise_on_failure=True)
        self.assertIsNotNone(context.exception.report)

    def test_tolerance_graph_roundtrip_and_dangling_refs(self):
        width = scad.var("width", 10.0, tolerance=0.1)
        expression_graph = scad.ExpressionGraph()
        tolerance_graph = scad.ToleranceGraph(expression_graph)
        requirement = tolerance_graph.require(
            width * 2.0, 0.2, name="overall_width", requirement_id="req_width"
        )

        expression_payload = expression_graph.to_dict()
        rebuilt_expression_graph = scad.ExpressionGraph.from_dict(expression_payload)
        rebuilt = scad.ToleranceGraph.from_dict(
            tolerance_graph.to_dict(), rebuilt_expression_graph
        )

        self.assertEqual(rebuilt.requirement_count, 1)
        self.assertEqual(rebuilt.requirements[0], requirement)
        broken = tolerance_graph.to_dict()
        broken["requirements"][0]["target_expr_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "Unknown tolerance target"):
            scad.ToleranceGraph.from_dict(broken, rebuilt_expression_graph)

    def test_tolerance_graph_rejects_malformed_requirement_types(self):
        width = scad.var("width", 10.0, tolerance=0.1)
        expression_graph = scad.ExpressionGraph()
        expression_graph.register(width)
        base = {
            "requirements": [
                {
                    "requirement_id": "req_width",
                    "target_expr_id": width.expr_id,
                    "tolerance": {
                        "lower_deviation": -0.1,
                        "upper_deviation": 0.1,
                    },
                    "method": "worst_case",
                    "name": "width",
                }
            ]
        }

        for field, invalid in (
            ("requirement_id", 1),
            ("target_expr_id", 1),
            ("method", []),
            ("name", 1),
            ("name", ""),
        ):
            payload = json.loads(json.dumps(base))
            payload["requirements"][0][field] = invalid
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                scad.ToleranceGraph.from_dict(payload, expression_graph)

    def test_duplicate_requirement_ids_are_rejected(self):
        width = scad.var("width", 10.0, tolerance=0.1)
        graph = scad.ToleranceGraph(scad.ExpressionGraph())
        graph.require(width, 0.1, requirement_id="same")

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            graph.require(width, 0.1, requirement_id="same")

    def test_explicit_invalid_requirement_ids_and_names_are_rejected(self):
        width = scad.var("width", 10.0, tolerance=0.1)
        graph = scad.ToleranceGraph(scad.ExpressionGraph())

        for requirement_id in ("", 0, []):
            with self.subTest(requirement_id=requirement_id), self.assertRaises(
                (TypeError, ValueError)
            ):
                graph.require(width, 0.1, requirement_id=requirement_id)
        with self.assertRaises(ValueError):
            graph.require(width, 0.1, name="")

    def test_session_and_model_json_include_tolerance_graph(self):
        width = scad.var("width", 10.0, tolerance=(-0.1, 0.2))
        with scad.GraphSession() as session:
            session.require_tolerance(width * 2.0, (-0.2, 0.4), name="overall")

        session_payload = scad.import_session_json(scad.export_session_json(session))
        model_payload = scad.import_model_json(scad.export_model_json(session))

        self.assertEqual(session_payload["tolerance_graph"].requirement_count, 1)
        self.assertTrue(session_payload["tolerance_graph"].validate().passed)
        self.assertEqual(model_payload["tolerance_graph"].requirement_count, 1)

    def test_legacy_session_and_model_payloads_default_to_empty_tolerance_graph(self):
        with scad.GraphSession() as session:
            pass
        raw_session = json.loads(scad.export_session_json(session))
        raw_model = json.loads(scad.export_model_json(session))
        raw_session.pop("tolerance_graph")
        raw_model.pop("tolerance_graph")

        imported_session = scad.import_session_json(json.dumps(raw_session))
        imported_model = scad.import_model_json(json.dumps(raw_model))

        self.assertEqual(imported_session["tolerance_graph"].requirement_count, 0)
        self.assertEqual(imported_model["tolerance_graph"].requirement_count, 0)

    def test_failed_requirement_blocks_session_and_model_export(self):
        width = scad.var("width", 10.0, tolerance=0.2)
        with scad.GraphSession() as session:
            session.require_tolerance(width, 0.1, name="width")

        with self.assertRaises(scad.ToleranceValidationError):
            scad.export_session_json(session)
        with self.assertRaises(scad.SimpleCADError):
            scad.export_model_json(session)

    def test_failed_requirement_in_hand_edited_model_blocks_replay(self):
        width = scad.var("width", 10.0, tolerance=0.2)
        with scad.GraphSession() as session:
            scad.make_box_rsolid(width, 1.0, 1.0)
            session.require_tolerance(width, 0.2, name="width")
        payload = json.loads(scad.export_model_json(session))
        payload["tolerance_graph"]["requirements"][0]["tolerance"] = {
            "lower_deviation": -0.1,
            "upper_deviation": 0.1,
        }

        with self.assertRaises(scad.SimpleCADError):
            scad.replay_model_json(json.dumps(payload))

    def test_analysis_and_report_payloads_are_json_serializable(self):
        width = scad.var("width", 10.0, tolerance=0.1)
        check = scad.check_tolerance(width * 2.0, 0.2, name="overall")

        serialized = json.dumps(check.to_dict())

        self.assertIn('"passed": true', serialized)
        self.assertIn('"variable_name": "width"', serialized)

    def test_unknown_method_is_rejected(self):
        width = scad.var("width", 10.0, tolerance=0.1)

        with self.assertRaisesRegex(ValueError, "Unsupported"):
            scad.analyze_tolerance(width, method="monte_carlo")


if __name__ == "__main__":
    unittest.main()
