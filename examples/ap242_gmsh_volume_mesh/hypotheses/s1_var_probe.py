"""S1 Role 4 hypothesis: Var-declared params feed primitive calls.

Checks: (a) scad.var values evaluate in scalar argument positions of
make_box_rsolid / make_cylinder_rsolid; (b) tuple argument positions
(bottom_face_center) need plain floats -> derive via .evaluate();
(c) resulting dims match the legacy plain-float build exactly.
"""

from __future__ import annotations

import simplecadapi as scad

WIDTH = scad.var("bracket_width", 40.0, unit="mm")
HEIGHT = scad.var("bracket_height", 36.0, unit="mm")
RATIO = scad.var("mount_hole_height_ratio", 0.62)
RADIUS = scad.var("mount_hole_radius", 2.5, unit="mm", tolerance=0.1)


def _f(scalar) -> float:
    """Evaluate any ScalarLike (Var/Expr/float) to a plain canonical float."""
    return float(scalar.evaluate()) if hasattr(scalar, "evaluate") else float(scalar)


def main() -> None:
    with scad.GraphSession(graph_id="s1_var_probe"):
        # (a) Var in scalar positions, expression arithmetic stays lazy
        wall = scad.make_box_rsolid(
            width=scad.var("plate_thickness", 4.0, unit="mm"),
            height=WIDTH,
            depth=HEIGHT,
            bottom_face_center=(0.0, 0.0, 0.0),
        )
        volume = wall.get_volume()
        print("wall volume", volume)
        assert abs(volume - 4.0 * 40.0 * 36.0) < 1e-9, volume

        # (b) finding: unit-declared Var * unitless Var builds lazily, but
        #     .evaluate() raises UnitValidationError ("mixes unit-declared
        #     variables with legacy variables"). Derived values must be
        #     computed in plain-float space via _f().
        try:
            float((HEIGHT * RATIO).evaluate())
            raise SystemExit("expected UnitValidationError was not raised")
        except SystemExit:
            raise
        except Exception as error:  # noqa: BLE001 - probing documented failure
            print("mixed-unit expr rejected at evaluate():", type(error).__name__)
        z = _f(HEIGHT) * _f(RATIO)
        center = (0.0, 0.0, z)
        tool = scad.make_cylinder_rsolid(
            radius=RADIUS,
            height=10.0,
            bottom_face_center=center,
            axis=(1.0, 0.0, 0.0),
        )
        tool_volume = tool.get_volume()
        print("tool volume", tool_volume, "center z", center)
        assert abs(tool_volume - 3.141592653589793 * 2.5 * 2.5 * 10.0) < 1e-6
        assert abs(center[2] - 22.32) < 1e-9, center

    print("H1 ADOPTED: Var ok in scalar positions; derived coords via plain-float _f()")


if __name__ == "__main__":
    main()
