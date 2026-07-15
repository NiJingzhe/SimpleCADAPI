from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple
import uuid


TAG_BINDING_SCHEMA_VERSION = "1.0"

_TAG_SEGMENT = r"[a-z][a-z0-9_-]*"
_TAG_RE = re.compile(rf"^{_TAG_SEGMENT}(?:\.{_TAG_SEGMENT})*$")


class TagScope(str, Enum):
    """Supported projections of the semantic binding store."""

    LOCAL = "local"
    INHERITED = "inherited"
    EFFECTIVE = "effective"
    LINEAGE = "lineage"


class TopologyPropagation(str, Enum):
    LOCAL = "local"
    DOWNWARD = "downward"


class LineagePolicy(str, Enum):
    NONE = "none"
    CONTINUATION = "continuation"
    CONTINUATION_FRAGMENT = "continuation_fragment"
    EXPLICIT = "explicit"


class LineageDerivation(str, Enum):
    CONTINUATION = "continuation"
    FRAGMENT = "fragment"
    MERGE = "merge"
    INTERSECTION = "intersection"
    BOUNDARY = "boundary"
    REPLACEMENT = "replacement"


class TagAttachment(str, Enum):
    LOCAL = "local"
    INHERITED = "inherited"
    EFFECTIVE_LEGACY = "effective_legacy"


class TagProducerKind(str, Enum):
    USER_OPERATION = "user_operation"
    AUTO_RULE = "auto_rule"
    IMPORTED_SIDECAR = "imported_sidecar"
    LEGACY_IMPORT = "legacy_import"


class TagTargetKind(str, Enum):
    SELECTION_QUERY = "selection_query"
    SCOPE_ROOT = "scope_root"
    EXPLICIT_REFS = "explicit_refs"
    LEGACY_EFFECTIVE = "legacy_effective"


class TagEvidenceKind(str, Enum):
    USER_ASSERTION = "user_assertion"
    QUERY_EXECUTION = "query_execution"
    TOPOLOGY_CHANGE = "topology_change"
    GEOMETRY_CLASSIFICATION = "geometry_classification"
    IMPORTED_SIDECAR = "imported_sidecar"
    LEGACY_SNAPSHOT = "legacy_snapshot"


class TagCertainty(str, Enum):
    ASSERTED = "asserted"
    PROVEN = "proven"


class TagLifecycle(str, Enum):
    ASSERTION = "assertion"
    RECOMPUTE = "recompute"
    SNAPSHOT = "snapshot"


VALID_TAG_SCOPES = frozenset(scope.value for scope in TagScope)


class TagValidationError(ValueError):
    """Raised when a tag binding or policy is malformed."""


class SemanticCapabilityError(ValueError):
    """Raised when an object cannot evaluate a requested semantic scope."""


class UnsupportedQueryCapabilityError(SemanticCapabilityError):
    """Raised when required query evidence is unavailable or incomplete."""


def _as_enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TagValidationError(f"{field_name} must be a string or {enum_type.__name__}")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(sorted(item.value for item in enum_type))
        raise TagValidationError(
            f"unsupported {field_name} '{value}'; expected one of: {allowed}"
        ) from exc


def _strict_mapping(
    name: str,
    data: Mapping[str, Any],
    *,
    required: Tuple[str, ...],
    optional: Tuple[str, ...] = (),
) -> None:
    if not isinstance(data, Mapping):
        raise TagValidationError(f"{name} must be an object")
    keys = set(data)
    missing = set(required) - keys
    unknown = keys - set(required) - set(optional)
    if missing:
        raise TagValidationError(
            f"{name} is missing required field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise TagValidationError(
            f"{name} contains unknown field(s): {', '.join(sorted(unknown))}"
        )


def _optional_string(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TagValidationError(f"{field_name} must be null or a non-empty string")
    return value


def normalize_tag_scope(scope: str | TagScope) -> TagScope:
    if isinstance(scope, TagScope):
        return scope
    if not isinstance(scope, str):
        raise TypeError("tag scope must be a string or TagScope")
    try:
        return TagScope(scope.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(sorted(VALID_TAG_SCOPES))
        raise ValueError(
            f"unsupported tag scope '{scope}'; expected one of: {allowed}"
        ) from exc


@dataclass(frozen=True)
class TagBindingScope:
    """Snapshot boundary in which an assignment target is evaluated."""

    node_id: Optional[str] = None
    output_slot: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _optional_string(self.node_id, "scope.node_id"))
        if isinstance(self.output_slot, bool) or not isinstance(self.output_slot, int):
            raise TagValidationError("scope.output_slot must be an integer")
        if self.output_slot < 0:
            raise TagValidationError("scope.output_slot must be >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id, "output_slot": self.output_slot}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagBindingScope":
        _strict_mapping(
            "TagBinding.scope", data, required=("node_id", "output_slot")
        )
        return cls(node_id=data["node_id"], output_slot=data["output_slot"])


@dataclass(frozen=True)
class TagProducer:
    """Identity of the operation, rule, or import that made an assertion."""

    kind: TagProducerKind | str
    node_id: Optional[str] = None
    rule_id: Optional[str] = None
    rule_version: Optional[str] = None

    def __post_init__(self) -> None:
        kind = _as_enum(self.kind, TagProducerKind, "producer kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self, "node_id", _optional_string(self.node_id, "producer.node_id")
        )
        object.__setattr__(
            self, "rule_id", _optional_string(self.rule_id, "producer.rule_id")
        )
        object.__setattr__(
            self,
            "rule_version",
            _optional_string(self.rule_version, "producer.rule_version"),
        )
        if kind == TagProducerKind.AUTO_RULE and (
            self.rule_id is None or self.rule_version is None
        ):
            raise TagValidationError(
                "auto_rule producers require rule_id and rule_version"
            )
        if kind != TagProducerKind.AUTO_RULE and (
            self.rule_id is not None or self.rule_version is not None
        ):
            raise TagValidationError(
                "rule_id and rule_version are only valid for auto_rule producers"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "node_id": self.node_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagProducer":
        _strict_mapping(
            "TagBinding.producer",
            data,
            required=("kind", "node_id", "rule_id", "rule_version"),
        )
        return cls(
            kind=data["kind"],
            node_id=data["node_id"],
            rule_id=data["rule_id"],
            rule_version=data["rule_version"],
        )


@dataclass(frozen=True)
class TagTarget:
    """Serializable assignment intent, separate from execution evidence."""

    kind: TagTargetKind | str = TagTargetKind.SCOPE_ROOT
    query_hash: Optional[str] = None
    binding_hash: Optional[str] = None
    selector: Optional[Dict[str, Any]] = None
    refs: Tuple[Dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        kind = _as_enum(self.kind, TagTargetKind, "target kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "query_hash",
            _optional_string(self.query_hash, "target.query_hash"),
        )
        object.__setattr__(
            self,
            "binding_hash",
            _optional_string(self.binding_hash, "target.binding_hash"),
        )
        if self.selector is not None and not isinstance(self.selector, dict):
            raise TagValidationError("target.selector must be an object")
        if not isinstance(self.refs, tuple) or not all(
            isinstance(ref, dict) for ref in self.refs
        ):
            raise TagValidationError("target.refs must be a tuple of objects")

        if kind == TagTargetKind.SELECTION_QUERY:
            if self.selector is None and self.query_hash is None:
                raise TagValidationError(
                    "selection_query targets require selector or query_hash"
                )
            if (self.query_hash is None) != (self.binding_hash is None):
                raise TagValidationError(
                    "selection_query query_hash and binding_hash must be provided together"
                )
            if self.refs:
                raise TagValidationError(
                    "selection_query target refs belong in execution evidence"
                )
        elif kind == TagTargetKind.EXPLICIT_REFS:
            if not self.refs:
                raise TagValidationError("explicit_refs targets require refs")
            if any(
                value is not None
                for value in (self.query_hash, self.binding_hash, self.selector)
            ):
                raise TagValidationError(
                    "explicit_refs targets cannot contain query fields"
                )
        elif kind == TagTargetKind.LEGACY_EFFECTIVE:
            if any(
                value is not None
                for value in (self.query_hash, self.binding_hash, self.selector)
            ):
                raise TagValidationError(
                    "legacy_effective targets cannot contain query fields"
                )
        elif any(
            value is not None
            for value in (self.query_hash, self.binding_hash, self.selector)
        ) or self.refs:
            raise TagValidationError("scope_root targets cannot contain query fields or refs")

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"kind": self.kind.value}
        if self.query_hash is not None:
            payload["query_hash"] = self.query_hash
            payload["binding_hash"] = self.binding_hash
        if self.selector is not None:
            payload["selector"] = deepcopy(self.selector)
        if self.refs:
            payload["refs"] = deepcopy(list(self.refs))
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagTarget":
        if not isinstance(data, Mapping):
            raise TagValidationError("TagBinding.target must be an object")
        _strict_mapping(
            "TagBinding.target",
            data,
            required=("kind",),
            optional=("query_hash", "binding_hash", "selector", "refs"),
        )
        refs = data.get("refs", ())
        if not isinstance(refs, (list, tuple)) or not all(
            isinstance(ref, Mapping) for ref in refs
        ):
            raise TagValidationError("target.refs must be an array of objects")
        selector = data.get("selector")
        return cls(
            kind=data["kind"],
            query_hash=data.get("query_hash"),
            binding_hash=data.get("binding_hash"),
            selector=deepcopy(dict(selector)) if isinstance(selector, Mapping) else selector,
            refs=tuple(deepcopy(dict(ref)) for ref in refs),
        )


@dataclass(frozen=True)
class TagPropagation:
    topology: TopologyPropagation | str = TopologyPropagation.LOCAL
    lineage: LineagePolicy | str = LineagePolicy.CONTINUATION_FRAGMENT
    explicit_derivations: Tuple[LineageDerivation | str, ...] = ()

    def __post_init__(self) -> None:
        topology = _as_enum(
            self.topology, TopologyPropagation, "topology propagation"
        )
        lineage = _as_enum(self.lineage, LineagePolicy, "lineage policy")
        derivations = tuple(
            _as_enum(item, LineageDerivation, "lineage derivation")
            for item in self.explicit_derivations
        )
        object.__setattr__(self, "topology", topology)
        object.__setattr__(self, "lineage", lineage)
        object.__setattr__(self, "explicit_derivations", derivations)
        if lineage == LineagePolicy.EXPLICIT and not derivations:
            raise TagValidationError(
                "explicit lineage policy requires explicit_derivations"
            )
        if lineage != LineagePolicy.EXPLICIT and derivations:
            raise TagValidationError(
                "explicit_derivations are only valid with explicit lineage policy"
            )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "topology": self.topology.value,
            "lineage": self.lineage.value,
        }
        if self.explicit_derivations:
            payload["derivations"] = [
                derivation.value for derivation in self.explicit_derivations
            ]
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagPropagation":
        _strict_mapping(
            "TagBinding.propagation",
            data,
            required=("topology", "lineage"),
            optional=("derivations",),
        )
        derivations = data.get("derivations", ())
        if not isinstance(derivations, (list, tuple)):
            raise TagValidationError("propagation.derivations must be an array")
        return cls(
            topology=data["topology"],
            lineage=data["lineage"],
            explicit_derivations=tuple(derivations),
        )


@dataclass(frozen=True)
class TagEvidence:
    """Typed evidence payload for a binding or a lineage witness."""

    kind: TagEvidenceKind | str
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind", _as_enum(self.kind, TagEvidenceKind, "evidence kind")
        )
        if not isinstance(self.data, dict):
            raise TagValidationError("evidence data must be an object")
        if "kind" in self.data:
            raise TagValidationError("evidence data cannot redefine kind")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value, **deepcopy(self.data)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagEvidence":
        if not isinstance(data, Mapping):
            raise TagValidationError("TagBinding.evidence must be an object")
        if "kind" not in data:
            raise TagValidationError("TagBinding.evidence is missing required field: kind")
        return cls(
            kind=data["kind"],
            data=deepcopy({key: value for key, value in data.items() if key != "kind"}),
        )


@dataclass(frozen=True)
class TagBinding:
    """Canonical, source-preserving Semantic Binding Schema 1.0 assignment."""

    tag: str
    producer: TagProducer
    scope: TagBindingScope = field(default_factory=TagBindingScope)
    target: TagTarget = field(default_factory=TagTarget)
    propagation: TagPropagation = field(default_factory=TagPropagation)
    evidence: TagEvidence = field(
        default_factory=lambda: TagEvidence(TagEvidenceKind.USER_ASSERTION)
    )
    attachment: TagAttachment | str = TagAttachment.LOCAL
    certainty: TagCertainty | str = TagCertainty.ASSERTED
    lifecycle: TagLifecycle | str = TagLifecycle.ASSERTION
    binding_id: str = field(
        default_factory=lambda: f"tag_binding_{uuid.uuid4().hex}"
    )
    schema_version: str = TAG_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        try:
            normalized = normalize_tag(self.tag, strict=True)
        except (TypeError, ValueError) as exc:
            raise TagValidationError(str(exc)) from exc
        object.__setattr__(self, "tag", normalized)
        object.__setattr__(
            self, "attachment", _as_enum(self.attachment, TagAttachment, "attachment")
        )
        object.__setattr__(
            self, "certainty", _as_enum(self.certainty, TagCertainty, "certainty")
        )
        object.__setattr__(
            self, "lifecycle", _as_enum(self.lifecycle, TagLifecycle, "lifecycle")
        )
        if not isinstance(self.producer, TagProducer):
            raise TagValidationError("producer must be a TagProducer")
        if not isinstance(self.scope, TagBindingScope):
            raise TagValidationError("scope must be a TagBindingScope")
        if not isinstance(self.target, TagTarget):
            raise TagValidationError("target must be a TagTarget")
        if not isinstance(self.propagation, TagPropagation):
            raise TagValidationError("propagation must be a TagPropagation")
        if not isinstance(self.evidence, TagEvidence):
            raise TagValidationError("evidence must be TagEvidence")
        if self.schema_version != TAG_BINDING_SCHEMA_VERSION:
            raise TagValidationError(
                f"unsupported TagBinding schema_version '{self.schema_version}'"
            )
        if not isinstance(self.binding_id, str) or not self.binding_id:
            raise TagValidationError("binding_id must be a non-empty string")
        if self.attachment == TagAttachment.INHERITED:
            raise TagValidationError(
                "inherited is a computed attachment and cannot be stored in TagBinding"
            )
        if self.attachment == TagAttachment.EFFECTIVE_LEGACY:
            if self.producer.kind != TagProducerKind.LEGACY_IMPORT:
                raise TagValidationError(
                    "effective_legacy bindings require a legacy_import producer"
                )
            if self.target.kind != TagTargetKind.LEGACY_EFFECTIVE:
                raise TagValidationError(
                    "effective_legacy bindings require a legacy_effective target"
                )
            if self.propagation.lineage != LineagePolicy.NONE:
                raise TagValidationError(
                    "legacy effective bindings cannot claim lineage"
                )
            if self.lifecycle != TagLifecycle.SNAPSHOT:
                raise TagValidationError(
                    "legacy effective bindings require snapshot lifecycle"
                )
            if self.evidence.kind != TagEvidenceKind.LEGACY_SNAPSHOT:
                raise TagValidationError(
                    "legacy effective bindings require legacy_snapshot evidence"
                )
        elif self.target.kind == TagTargetKind.LEGACY_EFFECTIVE:
            raise TagValidationError(
                "legacy_effective targets require effective_legacy attachment"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "binding_id": self.binding_id,
            "tag": self.tag,
            "producer": self.producer.to_dict(),
            "scope": self.scope.to_dict(),
            "target": self.target.to_dict(),
            "attachment": self.attachment.value,
            "propagation": self.propagation.to_dict(),
            "evidence": self.evidence.to_dict(),
            "certainty": self.certainty.value,
            "lifecycle": self.lifecycle.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagBinding":
        _strict_mapping(
            "TagBinding",
            data,
            required=(
                "schema_version",
                "binding_id",
                "tag",
                "producer",
                "scope",
                "target",
                "attachment",
                "propagation",
                "evidence",
                "certainty",
                "lifecycle",
            ),
        )
        try:
            return cls(
                schema_version=data["schema_version"],
                binding_id=data["binding_id"],
                tag=data["tag"],
                producer=TagProducer.from_dict(data["producer"]),
                scope=TagBindingScope.from_dict(data["scope"]),
                target=TagTarget.from_dict(data["target"]),
                attachment=data["attachment"],
                propagation=TagPropagation.from_dict(data["propagation"]),
                evidence=TagEvidence.from_dict(data["evidence"]),
                certainty=data["certainty"],
                lifecycle=data["lifecycle"],
            )
        except TagValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise TagValidationError("invalid TagBinding payload") from exc


@dataclass(frozen=True)
class TagLineageWitness:
    """Evidence that makes a source binding visible in lineage scope."""

    binding: TagBinding
    derivation: LineageDerivation | str
    source_topo_id: str
    target_topo_id: str
    evidence: TagEvidence
    coverage: str = "complete"

    def __post_init__(self) -> None:
        if not isinstance(self.binding, TagBinding):
            raise TagValidationError("lineage witness binding must be a TagBinding")
        object.__setattr__(
            self,
            "derivation",
            _as_enum(self.derivation, LineageDerivation, "lineage derivation"),
        )
        for field_name in ("source_topo_id", "target_topo_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TagValidationError(f"{field_name} must be a non-empty string")
        if not isinstance(self.evidence, TagEvidence):
            raise TagValidationError("lineage witness evidence must be TagEvidence")
        if self.coverage not in {"complete", "partial", "none"}:
            raise TagValidationError(
                "lineage witness coverage must be complete, partial, or none"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "binding": self.binding.to_dict(),
            "derivation": self.derivation.value,
            "source_topo_id": self.source_topo_id,
            "target_topo_id": self.target_topo_id,
            "evidence": self.evidence.to_dict(),
            "coverage": self.coverage,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagLineageWitness":
        _strict_mapping(
            "TagLineageWitness",
            data,
            required=(
                "binding",
                "derivation",
                "source_topo_id",
                "target_topo_id",
                "evidence",
                "coverage",
            ),
        )
        try:
            return cls(
                binding=TagBinding.from_dict(data["binding"]),
                derivation=data["derivation"],
                source_topo_id=data["source_topo_id"],
                target_topo_id=data["target_topo_id"],
                evidence=TagEvidence.from_dict(data["evidence"]),
                coverage=data["coverage"],
            )
        except TagValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise TagValidationError("invalid TagLineageWitness payload") from exc


def lineage_policy_allows(
    policy: LineagePolicy | TagPropagation,
    derivation: str | LineageDerivation,
) -> bool:
    propagation = policy if isinstance(policy, TagPropagation) else None
    lineage = propagation.lineage if propagation is not None else policy
    lineage = _as_enum(lineage, LineagePolicy, "lineage policy")
    derivation_value = _as_enum(
        derivation, LineageDerivation, "lineage derivation"
    )
    if lineage == LineagePolicy.NONE:
        return False
    if lineage == LineagePolicy.CONTINUATION:
        return derivation_value == LineageDerivation.CONTINUATION
    if lineage == LineagePolicy.CONTINUATION_FRAGMENT:
        return derivation_value in {
            LineageDerivation.CONTINUATION,
            LineageDerivation.FRAGMENT,
        }
    if propagation is None:
        return False
    return derivation_value in propagation.explicit_derivations


def user_tag_binding(
    tag: str,
    *,
    node_id: Optional[str] = None,
    scope_node_id: Optional[str] = None,
    output_slot: int = 0,
    target: Optional[TagTarget] = None,
    topology: TopologyPropagation | str = TopologyPropagation.LOCAL,
    lineage: LineagePolicy | str = LineagePolicy.CONTINUATION_FRAGMENT,
    explicit_derivations: Tuple[LineageDerivation | str, ...] = (),
    evidence: Optional[TagEvidence] = None,
) -> TagBinding:
    """Create a canonical user assertion with explicit frozen policies."""

    return TagBinding(
        tag=tag,
        producer=TagProducer(TagProducerKind.USER_OPERATION, node_id=node_id),
        scope=TagBindingScope(
            node_id=node_id if scope_node_id is None else scope_node_id,
            output_slot=output_slot,
        ),
        target=target or TagTarget(TagTargetKind.SCOPE_ROOT),
        propagation=TagPropagation(
            topology=topology,
            lineage=lineage,
            explicit_derivations=explicit_derivations,
        ),
        evidence=evidence
        or TagEvidence(
            TagEvidenceKind.USER_ASSERTION,
            {"authoring_source": "simplecadapi.apply_tag"},
        ),
        certainty=TagCertainty.ASSERTED,
        lifecycle=TagLifecycle.ASSERTION,
    )


def internal_tag_binding(
    tag: str,
    *,
    topology: TopologyPropagation | str = TopologyPropagation.LOCAL,
    rule_id: str = "simplecad.compat.internal_annotation",
    rule_version: str = "1.0",
    evidence: Optional[Dict[str, Any]] = None,
) -> TagBinding:
    """Create a source-marked binding for transitional internal annotations."""

    return TagBinding(
        tag=tag,
        producer=TagProducer(
            TagProducerKind.AUTO_RULE,
            rule_id=rule_id,
            rule_version=rule_version,
        ),
        propagation=TagPropagation(
            topology=topology,
            lineage=LineagePolicy.NONE,
        ),
        evidence=TagEvidence(
            TagEvidenceKind.LEGACY_SNAPSHOT,
            {"source": "internal_annotation", **dict(evidence or {})},
        ),
        certainty=TagCertainty.PROVEN,
        lifecycle=TagLifecycle.SNAPSHOT,
    )


def operation_role_tag_binding(
    tag: str,
    *,
    operation: str,
    role: str,
    target_topo_id: str,
    evidence_method: str,
) -> TagBinding:
    """Create a deterministic binding for a kernel-proven output role."""

    rule_id = "simplecad.operation_output_role"
    binding_key = "|".join(
        (rule_id, str(operation), str(role), str(target_topo_id), str(tag))
    )
    return TagBinding(
        tag=tag,
        producer=TagProducer(
            TagProducerKind.AUTO_RULE,
            rule_id=rule_id,
            rule_version="1.0",
        ),
        target=TagTarget(TagTargetKind.SCOPE_ROOT),
        propagation=TagPropagation(
            topology=TopologyPropagation.LOCAL,
            lineage=LineagePolicy.CONTINUATION_FRAGMENT,
        ),
        evidence=TagEvidence(
            TagEvidenceKind.TOPOLOGY_CHANGE,
            {
                "operation": str(operation),
                "result_role": str(role),
                "target_topo_id": str(target_topo_id),
                "evidence_method": str(evidence_method),
            },
        ),
        certainty=TagCertainty.PROVEN,
        lifecycle=TagLifecycle.RECOMPUTE,
        binding_id=f"tag_binding_{uuid.uuid5(uuid.NAMESPACE_URL, binding_key).hex}",
    )


def projected_tag_binding(
    source: TagBinding,
    *,
    operation: str,
    role: str,
    source_topo_id: str,
    target_topo_id: str,
    evidence_method: str,
) -> TagBinding:
    """Project one source binding through a proven feature-generation witness."""

    if not isinstance(source, TagBinding):
        raise TypeError("source must be a TagBinding")
    rule_id = "simplecad.feature_source_tag_projection"
    binding_key = "|".join(
        (
            rule_id,
            source.binding_id,
            str(operation),
            str(role),
            str(source_topo_id),
            str(target_topo_id),
        )
    )
    return TagBinding(
        tag=source.tag,
        producer=TagProducer(
            TagProducerKind.AUTO_RULE,
            rule_id=rule_id,
            rule_version="1.0",
        ),
        target=TagTarget(TagTargetKind.SCOPE_ROOT),
        propagation=TagPropagation(
            topology=TopologyPropagation.LOCAL,
            lineage=source.propagation.lineage,
            explicit_derivations=source.propagation.explicit_derivations,
        ),
        evidence=TagEvidence(
            TagEvidenceKind.TOPOLOGY_CHANGE,
            {
                "operation": str(operation),
                "result_role": str(role),
                "source_binding_id": source.binding_id,
                "source_topo_id": str(source_topo_id),
                "target_topo_id": str(target_topo_id),
                "evidence_method": str(evidence_method),
            },
        ),
        certainty=TagCertainty.PROVEN,
        lifecycle=TagLifecycle.RECOMPUTE,
        binding_id=f"tag_binding_{uuid.uuid5(uuid.NAMESPACE_URL, binding_key).hex}",
    )


def legacy_tag_binding(tag: str, *, diagnostic: Optional[str] = None) -> TagBinding:
    """Import one flat compatibility token without inventing assignment intent."""

    evidence: Dict[str, Any] = {"imported_tags": [tag]}
    if diagnostic is not None:
        evidence["migration_diagnostic"] = str(diagnostic)
    return TagBinding(
        tag=tag,
        producer=TagProducer(TagProducerKind.LEGACY_IMPORT),
        target=TagTarget(TagTargetKind.LEGACY_EFFECTIVE),
        attachment=TagAttachment.EFFECTIVE_LEGACY,
        propagation=TagPropagation(
            topology=TopologyPropagation.LOCAL,
            lineage=LineagePolicy.NONE,
        ),
        evidence=TagEvidence(TagEvidenceKind.LEGACY_SNAPSHOT, evidence),
        certainty=TagCertainty.ASSERTED,
        lifecycle=TagLifecycle.SNAPSHOT,
    )


def is_normalized_tag(tag: str) -> bool:
    """Check whether a tag matches the normalized dot-token format."""

    if not isinstance(tag, str):
        return False
    return bool(_TAG_RE.fullmatch(tag))


def normalize_tag(tag: str, *, strict: bool = True) -> str:
    """Normalize or strictly validate a tag."""

    if not isinstance(tag, str):
        raise TypeError("tag must be a string")
    cleaned = tag.strip()
    if strict:
        if not is_normalized_tag(cleaned):
            raise ValueError(f"tag '{tag}' is not normalized")
        return cleaned

    lowered = cleaned.lower()
    lowered = re.sub(r"\s+", "_", lowered)
    lowered = lowered.replace(":", "_")
    lowered = lowered.replace("/", ".")
    if not is_normalized_tag(lowered):
        raise ValueError(f"tag '{tag}' cannot be normalized")
    return lowered


@dataclass(frozen=True)
class TagPolicy:
    """Legacy token registry hints; canonical assignments do not consult this."""

    propagate_prefixes: tuple[str, ...] = (
        "role.",
        "anchor.",
        "group.",
    )
    propagate_exact: tuple[str, ...] = (
        "top",
        "bottom",
        "left",
        "right",
        "front",
        "back",
        "side",
        "surface",
    )
    block_prefixes: tuple[str, ...] = (
        "feature.",
        "state.",
        "face.",
        "edge.",
        "wire.",
        "vertex.",
        "solid.",
        "legacy.",
    )
    block_exact: tuple[str, ...] = ()

    def should_propagate(self, tag: str) -> bool:
        """Return the old registry hint without changing assignment policy."""

        if tag in self.block_exact:
            return False
        if any(tag.startswith(prefix) for prefix in self.block_prefixes):
            return False
        if tag in self.propagate_exact:
            return True
        return any(tag.startswith(prefix) for prefix in self.propagate_prefixes)


DEFAULT_TAG_POLICY = TagPolicy()


def resolve_anchor_tag_candidates(tag: str) -> List[str]:
    """Generate candidate tags for legacy anchor lookup."""

    token = tag.strip().lower()
    if not token:
        return []

    topology_prefixes = ("face.", "edge.", "wire.", "vertex.", "solid.")
    if is_normalized_tag(token) and "." in token:
        if token.startswith("role."):
            bare = token[len("role.") :]
        elif token.startswith("anchor."):
            bare = token[len("anchor.") :]
        elif any(token.startswith(prefix) for prefix in topology_prefixes):
            bare = token.split(".", 1)[1]
        elif token.startswith("legacy."):
            bare = token[len("legacy.") :]
        else:
            return [token]
        return [
            f"role.{bare}",
            f"anchor.{bare}",
            *(f"{prefix}{bare}" for prefix in topology_prefixes),
            f"legacy.{bare}",
            bare,
        ]

    return [
        f"role.{token}",
        f"anchor.{token}",
        f"face.{token}",
        f"edge.{token}",
        f"wire.{token}",
        f"vertex.{token}",
        f"solid.{token}",
        f"legacy.{token}",
        token,
    ]


# Short aliases retained for callers that use the model names rather than the
# field-qualified names.
BindingScope = TagBindingScope
Propagation = TagPropagation
Lineage = LineagePolicy
Attachment = TagAttachment
Producer = TagProducer
ProducerKind = TagProducerKind
Target = TagTarget
TargetKind = TagTargetKind
Evidence = TagEvidence
EvidenceKind = TagEvidenceKind
Certainty = TagCertainty
Lifecycle = TagLifecycle
