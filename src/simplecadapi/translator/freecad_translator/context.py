"""Per-translation compiler state for the FreeCAD backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ...topology import OperationGraph


@dataclass
class FreeCADCompileContext:
    """Mutable state owned by one FreeCAD script compilation."""

    document_name: str
    source_graph: Optional[OperationGraph] = None
    expression_aliases: Dict[str, str] = field(default_factory=dict)
    result_node_ids: Set[str] = field(default_factory=set)
    result_node_id_list: List[str] = field(default_factory=list)
    suppressed_profile_node_ids: Set[str] = field(default_factory=set)


__all__ = ["FreeCADCompileContext"]
