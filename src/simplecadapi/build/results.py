"""Typed build results and cache diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from ..artifacts.assembly_definition import AssemblyDefinition
from ..artifacts.feature_graph import FeatureGraphArtifact
from ..artifacts.interface import PartInterfaceDiff
from ..artifacts.part_definition import PartDefinition
from ..assembly import Assembly
from ..part import Part
from .incremental_solver import AssemblySolveReport


@dataclass(frozen=True, slots=True)
class CacheReport:
    """Per-build whole-part cache outcome."""

    mode: str
    build_key: str
    part_lookups: int
    part_hits: int
    part_misses: int
    corrupt_entries: int = 0
    miss_reason: str | None = None
    bytes_read: int = 0
    bytes_written: int = 0

    @property
    def hit(self) -> bool:
        return self.part_hits == 1


@dataclass(frozen=True)
class PartBuildResult:
    """Runtime Part plus its durable definition, feature DAG, and cache evidence."""

    value: Part
    definition: PartDefinition
    feature_graph: FeatureGraphArtifact
    cache_report: CacheReport
    interface_diff: PartInterfaceDiff | None = None

    def __post_init__(self) -> None:
        self.value._set_runtime("definition.content_hash", self.definition.content_hash)
        self.value._set_runtime("definition.kind", self.definition.definition_kind)
        self.value._set_runtime("definition.revision", self.definition.revision)

    @property
    def part(self) -> Part:
        return self.value

    def replay(self, *, strict: bool = True):
        return self.feature_graph.replay(strict=strict)




@dataclass(frozen=True)
class AssemblyBuildResult:
    """Runtime Assembly plus its durable definition, feature DAG, and solve evidence."""

    value: Assembly
    definition: AssemblyDefinition
    feature_graph: FeatureGraphArtifact
    solve_report: AssemblySolveReport

    def __post_init__(self) -> None:
        self.value._set_runtime("definition.content_hash", self.definition.content_hash)
        self.value._set_runtime("definition.kind", self.definition.definition_kind)
        self.value._set_runtime("definition.revision", self.definition.revision)

    @property
    def assembly(self) -> Assembly:
        return self.value

    def replay(self, *, strict: bool = True) -> Assembly:
        rebuilt = self.feature_graph.replay(
            strict=strict,
            external_definitions=self.definition.resolved_definitions,
        )
        if len(rebuilt) != 1 or not isinstance(rebuilt[0], Assembly):
            raise TypeError("assembly feature graph did not replay exactly one Assembly")
        return rebuilt[0]

__all__ = ["AssemblyBuildResult", "CacheReport", "PartBuildResult"]



