"""Product and assembly semantic value model plus its persistence layer.

Value classes: ``Placement`` → ``Connector`` → ``Constraint``/``Material``/
``Part`` → ``Assembly``, assembly solving (``solver``), and the canonical
persistence pipeline (``occurrence`` → ``packages`` → ``capture``).
"""

from .placement import Placement
from .connector import Connector, ConnectorAnchor, ConnectorRef, GeometryRef
from .constraint import Constraint, ConstraintReport, ConstraintResidual, ScalarLimit
from .material import Material
from .part import Part
from .assembly import Assembly, Component, PublicConnectorRef

__all__ = [
    "Assembly",
    "Component",
    "Connector",
    "ConnectorAnchor",
    "ConnectorRef",
    "Constraint",
    "ConstraintReport",
    "ConstraintResidual",
    "GeometryRef",
    "Material",
    "Part",
    "Placement",
    "PublicConnectorRef",
    "ScalarLimit",
]
