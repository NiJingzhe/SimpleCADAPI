"""Minimal Sketch object for the 2.0 rearchitecture path."""

from __future__ import annotations

from typing import Iterable, List

from .core import Edge, Face, TaggedMixin, TopoMixein, Wire


class Sketch(TaggedMixin, TopoMixein):
    """A lightweight first-class sketch container.

    Phase 1 scope:
    - hold 2D-ish curve inputs represented by Edge/Wire
    - expose them as stable children
    - optionally provide closed wires as profile candidates
    """

    def __init__(self, curves: Iterable[Edge | Wire] | None = None):
        TaggedMixin.__init__(self)
        TopoMixein.__init__(self, level=2, self_shape_ref=self)
        if curves is not None:
            for curve in curves:
                self.add_curve(curve)

    def add_curve(self, curve: Edge | Wire) -> "Sketch":
        if not isinstance(curve, (Edge, Wire)):
            raise ValueError("Sketch 仅支持 Edge 或 Wire 作为曲线输入")
        self.add_child(curve)
        return self

    def curves(self) -> List[Edge | Wire]:
        return list(self.get_children())

    def closed_wires(self) -> List[Wire]:
        result: List[Wire] = []
        for curve in self.curves():
            if isinstance(curve, Wire) and curve.is_closed():
                result.append(curve)
        return result

    def to_faces(self) -> List[Face]:
        from .operations import make_face_from_wire_rface

        return [make_face_from_wire_rface(wire) for wire in self.closed_wires()]
