"""Persistent PartDefinition and AssemblyDefinition artifact contracts."""

from .assembly_definition import AssemblyDefinition
from .assembly_io import (
    decode_assembly_definition,
    encode_assembly_definition,
    export_assembly_definition,
    load_assembly_definition,
    materialize_definition,
    validate_assembly_definition_graph,
)
from .canonical import (
    ARTIFACT_SCHEMA_VERSION,
    DEFAULT_ARTIFACT_LIMITS,
    ArtifactLimits,
    ArtifactValidationError,
)
from .geometry_interface import (
    geometry_interface_descriptor,
    geometry_interface_fingerprint,
)
from .interface import (
    PartInterfaceDiff,
    PartInterfaceSnapshot,
    diff_part_interfaces,
    load_latest_part_state,
    update_latest_part_state,
    write_latest_part_state,
)
from .part_definition import PartDefinition
from .part_io import (
    encode_part_definition,
    export_part_definition,
    load_part_definition,
)
from .references import (
    BlobRef,
    ConnectorInterface,
    FileInputSnapshot,
    InterfaceHashes,
    MaterialRef,
    PartInstance,
    PartRef,
)

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ArtifactLimits",
    "ArtifactValidationError",
    "AssemblyDefinition",
    "BlobRef",
    "PartInterfaceDiff",
    "PartInterfaceSnapshot",
    "decode_assembly_definition",
    "encode_assembly_definition",
    "export_assembly_definition",
    "load_assembly_definition",
    "materialize_definition",
    "validate_assembly_definition_graph",
    "ConnectorInterface",
    "encode_part_definition",
    "export_part_definition",
    "load_part_definition",
    "diff_part_interfaces",
    "geometry_interface_descriptor",
    "geometry_interface_fingerprint",
    "load_latest_part_state",
    "update_latest_part_state",
    "write_latest_part_state",
    "DEFAULT_ARTIFACT_LIMITS",
    "FileInputSnapshot",
    "InterfaceHashes",
    "MaterialRef",
    "PartInstance",
    "PartDefinition",
    "PartRef",
]
