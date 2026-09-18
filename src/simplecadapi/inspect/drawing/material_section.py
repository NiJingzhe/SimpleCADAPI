"""Compatibility entry for material-face section descriptors.

Explicit strategy selection lives in _section_geometry; no environment variable
controls the evidence path. Topological geometry is retained by _material_geometry.
"""

from ..brep.queries import _model, _section_source
from ._material_geometry import material_section_geometry


def material_section_descriptor(model, section, samples_per_edge):
    """Return the material-face descriptor using the shared geometry implementation."""
    source, _ = _section_source(_model(model), None)
    result, _, _, _ = material_section_geometry(
        source, section, samples_per_edge, section.get("tolerance", 1e-7)
    )
    return result
