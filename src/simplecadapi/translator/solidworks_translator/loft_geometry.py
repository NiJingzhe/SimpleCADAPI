"""Exact curve recipes for editable cross-kernel guided loft features."""
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_BSplineSurface
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS


def _curve_value(curve, first, last):
    curve = curve.Copy()
    curve.Segment(float(first), float(last))
    if curve.Degree() == 1 and curve.NbPoles() == 2:
        return {'kind': 'edge', 'type': 'line', 'start': list(curve.Pole(1).Coord()), 'end': list(curve.Pole(2).Coord())}
    return {
        'kind': 'edge', 'type': 'spline',
        'controls': [list(curve.Pole(i).Coord()) for i in range(1, curve.NbPoles()+1)],
        'degree': curve.Degree(),
        'knots': [curve.Knot(i) for i in range(1, curve.NbKnots()+1)],
        'multiplicities': [curve.Multiplicity(i) for i in range(1, curve.NbKnots()+1)],
        'weights': [curve.Weight(i) for i in range(1, curve.NbPoles()+1)],
        'periodic': curve.IsPeriodic(),
    }


def canonical_guided_loft(result):
    """Represent loft sides by exact boundary profiles and longitudinal guides.

    Linear cross-section spans need one guide at each boundary. Curved spans
    receive interior guides too. These become editable sketch splines in SW.
    """
    shape = getattr(result, 'wrapped', None)
    if shape is None or shape.IsNull():
        return None
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    sides = []
    while explorer.More():
        surface = BRepAdaptor_Surface(TopoDS.Face_s(explorer.Current()))
        if surface.GetType() == GeomAbs_BSplineSurface:
            sides.append(surface)
        explorer.Next()
    if not sides:
        return None
    # Interior isoparametric profiles also constrain cross-guide interpolation.
    # Nine stations stay below the observed dense-profile blend ceiling.
    profiles = [[] for _ in range(9)]
    guides = []
    guide_keys = set()
    for surface in sides:
        spline = surface.BSpline()
        u0, u1 = surface.FirstUParameter(), surface.LastUParameter()
        v0, v1 = surface.FirstVParameter(), surface.LastVParameter()
        for index in range(len(profiles)):
            v = v0 + (v1-v0) * index / (len(profiles)-1)
            profiles[index].append(_curve_value(spline.VIso(v), u0, u1))
        count = 1 if surface.UDegree() == 1 else 16
        for index in range(count + 1):
            u = u0 + (u1-u0) * index/count
            curve = spline.UIso(u)
            key = tuple(round(value, 8) for fraction in (0., .5, 1.) for value in curve.Value(v0+(v1-v0)*fraction).Coord())
            if key in guide_keys:
                continue
            guide_keys.add(key)
            guides.append(_curve_value(curve, v0, v1))
    return {'profiles': [{'kind': 'wire', 'edges': edges} for edges in profiles], 'guides': guides}
