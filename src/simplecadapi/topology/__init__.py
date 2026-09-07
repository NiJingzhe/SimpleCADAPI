"""Topology tracking data model and semantic tagging.

``model`` holds the serializable topology data model (``TopoRef``,
``TopoDelta``, ``OperationNode``, ``OperationGraph``, ``SemanticRef``, ...).
Its public symbols are re-exported here so ``from simplecadapi.topology
import ...`` keeps resolving the same names as the former ``topology``
module. ``tagging``/``tracking``/``autotag`` implement the semantic
projection pipeline on top of it.
"""

from .model import *  # noqa: F401,F403
