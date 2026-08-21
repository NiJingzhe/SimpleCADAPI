"""Reproducible Part and Assembly build entry points."""
from .assembly_builder import assemble
from .incremental_solver import AssemblySolveReport, ComponentSolveResult
from .dependencies import FileInput, file_input, snapshot_file_inputs
from .keys import (
    PART_CACHE_PROFILE,
    SEMANTIC_REGISTRY_VERSION,
    normalize_build_value,
    part_build_key,
)
from .part_builder import part
from .results import AssemblyBuildResult, CacheReport, PartBuildResult

__all__ = [
    "AssemblySolveReport",
    "ComponentSolveResult",
    "AssemblyBuildResult",
    "assemble",
    "PART_CACHE_PROFILE",
    "PartBuildResult",
    "SEMANTIC_REGISTRY_VERSION",
    "file_input",
    "normalize_build_value",
    "part",
    "part_build_key",
    "snapshot_file_inputs",
]
