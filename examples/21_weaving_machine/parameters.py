"""Source-bearing design values and fail-closed parameter gates."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from enum import Enum
from typing import Generic, TypeVar


T = TypeVar("T", int, float)


class EvidenceLevel(str, Enum):
    PDF_EXPLICIT = "pdf_explicit"
    FIGURE_RECONSTRUCTION = "figure_reconstruction"
    ENGINEERING_COMPLETION = "engineering_completion"


class ValidationStatus(str, Enum):
    PROPOSAL = "proposal"
    VALIDATED = "validated"


class DetailLevel(str, Enum):
    SKELETON = "skeleton"
    ENVELOPE = "envelope"
    REPRESENTATIVE = "representative"
    FULL = "full"


class ParameterValidationError(ValueError):
    """Raised with every failed parameter invariant, not only the first one."""

    def __init__(self, issues: list[str] | tuple[str, ...]):
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


@dataclass(frozen=True)
class DesignValue(Generic[T]):
    value: T
    unit: str
    evidence: EvidenceLevel
    status: ValidationStatus
    source: str
    revision: str = "design-10"
    external_evidence_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("DesignValue.value must be an int or float")
        if not math.isfinite(float(self.value)):
            raise ValueError("DesignValue.value must be finite")
        if (
            not self.unit.strip()
            or not self.source.strip()
            or not self.revision.strip()
        ):
            raise ValueError("unit, source, and revision must not be empty")
        if self.status is ValidationStatus.VALIDATED and not self.external_evidence_id:
            raise ValueError("validated values require external_evidence_id")


def _proposal(value: T, unit: str, source: str) -> DesignValue[T]:
    return DesignValue(
        value=value,
        unit=unit,
        evidence=EvidenceLevel.ENGINEERING_COMPLETION,
        status=ValidationStatus.PROPOSAL,
        source=source,
    )


def _pdf(value: T, unit: str, source: str) -> DesignValue[T]:
    return DesignValue(
        value=value,
        unit=unit,
        evidence=EvidenceLevel.PDF_EXPLICIT,
        status=ValidationStatus.PROPOSAL,
        source=source,
    )


@dataclass(frozen=True)
class MachineParameters:
    overall_length: DesignValue[float]
    overall_width: DesignValue[float]
    overall_height: DesignValue[float]
    base_datum_z: DesignValue[float]
    frame_half_width: DesignValue[float]
    supply_rack_x: DesignValue[float]
    guide_frame_half_height: DesignValue[float]
    takeup_travel: DesignValue[float]
    effective_width: DesignValue[float]
    guide_pitch: DesignValue[float]
    guide_positions: DesignValue[int]
    bias_angle_degrees: DesignValue[float]
    x_guide: DesignValue[float]
    x_needle: DesignValue[float]
    x_rapier: DesignValue[float]
    x_takeup: DesignValue[float]
    fill_half_height: DesignValue[float]
    rapier_thickness: DesignValue[float]
    rapier_clearance: DesignValue[float]
    yarn_height_allowance: DesignValue[float]
    rapier_left_clearance: DesignValue[float]
    rapier_right_clearance: DesignValue[float]
    dynamic_clearance: DesignValue[float]
    guide_block_width: DesignValue[float]
    guide_block_height: DesignValue[float]
    guide_block_depth: DesignValue[float]
    guide_eye_diameter: DesignValue[float]
    guide_rail_length: DesignValue[float]
    guide_slide_travel: DesignValue[float]
    bias_layers: DesignValue[int]
    filling_channels: DesignValue[int]
    fillings_per_cycle: DesignValue[int]

    @property
    def takeup_step(self) -> float:
        return self.guide_pitch.value / math.tan(
            math.radians(self.bias_angle_degrees.value)
        )

    @property
    def guide_center_span(self) -> float:
        return (self.guide_positions.value - 1) * self.guide_pitch.value

    @property
    def edge_allowance_total(self) -> float:
        return self.effective_width.value - self.guide_center_span

    @property
    def guide_centers_y(self) -> tuple[float, ...]:
        middle = (self.guide_positions.value - 1) / 2.0
        return tuple(
            (index - middle) * self.guide_pitch.value
            for index in range(self.guide_positions.value)
        )

    @property
    def filling_planes_z(self) -> tuple[float, float, float]:
        return (self.fill_half_height.value, 0.0, -self.fill_half_height.value)

    @property
    def minimum_shed_height(self) -> float:
        return (
            self.rapier_thickness.value
            + 2.0 * self.rapier_clearance.value
            + self.yarn_height_allowance.value
        )

    @property
    def minimum_rapier_travel(self) -> float:
        return (
            self.effective_width.value
            + self.rapier_left_clearance.value
            + self.rapier_right_clearance.value
        )

    def design_values(
        self,
    ) -> tuple[tuple[str, DesignValue[int] | DesignValue[float]], ...]:
        return tuple((item.name, getattr(self, item.name)) for item in fields(self))


def default_machine_parameters() -> MachineParameters:
    """Return the current concept values without promoting proposals to facts."""

    return MachineParameters(
        overall_length=_proposal(2400.0, "mm", "design/01:58-70"),
        overall_width=_proposal(1200.0, "mm", "design/01:58-70"),
        overall_height=_proposal(1900.0, "mm", "design/01:58-70"),
        base_datum_z=_proposal(-570.0, "mm", "design/02:155-168"),
        frame_half_width=_proposal(440.0, "mm", "design/02:59-67"),
        supply_rack_x=_proposal(-900.0, "mm", "PDF figure 3.20 reconstruction"),
        guide_frame_half_height=_proposal(
            130.0, "mm", "PDF figure 3.25 reconstruction"
        ),
        takeup_travel=_proposal(1000.0, "mm", "design/02:33-47"),
        effective_width=_proposal(300.0, "mm", "design/01:58-70"),
        guide_pitch=_proposal(12.0, "mm", "design/01:58-70"),
        guide_positions=_proposal(25, "count", "design/01:58-70"),
        bias_angle_degrees=_proposal(45.0, "degree", "design/01:58-91"),
        x_guide=_proposal(-360.0, "mm", "design/02:33-47"),
        x_needle=_proposal(-250.0, "mm", "design/02:33-47"),
        x_rapier=_proposal(-160.0, "mm", "design/02:33-47"),
        x_takeup=_proposal(300.0, "mm", "design/02:33-47"),
        fill_half_height=_proposal(24.0, "mm", "GAP-06 engineering completion"),
        rapier_thickness=_proposal(6.0, "mm", "GAP-06 engineering completion"),
        rapier_clearance=_proposal(5.0, "mm", "design/02:79-87"),
        yarn_height_allowance=_proposal(2.0, "mm", "GAP-06 engineering completion"),
        rapier_left_clearance=_proposal(120.0, "mm", "design/02:59-67"),
        rapier_right_clearance=_proposal(80.0, "mm", "design/02:59-67"),
        dynamic_clearance=_proposal(5.0, "mm", "design/02:139-153"),
        guide_block_width=_proposal(10.0, "mm", "design/03:62-72"),
        guide_block_height=_proposal(24.0, "mm", "design/03:62-72"),
        guide_block_depth=_proposal(22.0, "mm", "design/03:62-72"),
        guide_eye_diameter=_proposal(4.0, "mm", "D0 guide fixture proposal"),
        guide_rail_length=_proposal(60.0, "mm", "D1 guide fixture proposal"),
        guide_slide_travel=_proposal(12.0, "mm", "design/03:137-146"),
        bias_layers=_pdf(4, "count", "design/00:62"),
        filling_channels=_pdf(3, "count", "design/00:67"),
        fillings_per_cycle=_pdf(2, "count", "design/00:72"),
    )


def validate_concept_parameters(parameters: MachineParameters) -> None:
    issues: list[str] = []
    positive = (
        "overall_length",
        "overall_width",
        "overall_height",
        "frame_half_width",
        "takeup_travel",
        "effective_width",
        "guide_pitch",
        "fill_half_height",
        "rapier_thickness",
        "rapier_clearance",
        "guide_block_width",
        "guide_block_height",
        "guide_block_depth",
        "guide_eye_diameter",
        "guide_rail_length",
        "guide_slide_travel",
    )
    for name in positive:
        if getattr(parameters, name).value <= 0:
            issues.append(f"{name} must be greater than zero")
    if parameters.guide_positions.value < 2:
        issues.append("guide_positions must be at least 2")
    if not 0.0 < parameters.bias_angle_degrees.value < 90.0:
        issues.append("bias_angle_degrees must be between 0 and 90")
    if any(
        value.value < 0
        for value in (
            parameters.yarn_height_allowance,
            parameters.rapier_left_clearance,
            parameters.rapier_right_clearance,
            parameters.dynamic_clearance,
        )
    ):
        issues.append("clearances and yarn allowance must not be negative")
    if parameters.dynamic_clearance.value < 5.0:
        issues.append("dynamic_clearance must be at least 5 mm")
    if not (
        parameters.x_guide.value
        < parameters.x_needle.value
        < parameters.x_rapier.value
        < 0.0
        < parameters.x_takeup.value
    ):
        issues.append("X stations must satisfy X_G < X_N < X_R < 0 < X_T")
    if parameters.guide_center_span > parameters.effective_width.value:
        issues.append("guide center span exceeds effective width")
    if parameters.fill_half_height.value < parameters.minimum_shed_height:
        issues.append("fill_half_height is below the minimum shed-height contract")
    if parameters.bias_layers.value != 4:
        issues.append(
            "the source-backed machine architecture requires four bias layers"
        )
    if parameters.filling_channels.value != 3:
        issues.append(
            "the source-backed machine architecture requires three filling channels"
        )
    if parameters.fillings_per_cycle.value != 2:
        issues.append("the source-backed process requires two fillings per cycle")
    if issues:
        raise ParameterValidationError(issues)


def validate_manufacturing_release(parameters: MachineParameters) -> None:
    """Reject every proposal or validated value lacking external evidence."""

    validate_concept_parameters(parameters)
    issues = [
        f"{name} is not validated for manufacturing release"
        for name, value in parameters.design_values()
        if value.status is not ValidationStatus.VALIDATED
        or not value.external_evidence_id
    ]
    if issues:
        raise ParameterValidationError(issues)


def validate_detail_level(
    *,
    detail: DetailLevel,
    topology_closed: bool,
    inventory_complete: bool,
) -> None:
    if detail is DetailLevel.FULL and not topology_closed:
        raise ParameterValidationError(
            ["FULL requires closed_with_evidence guide topology"]
        )
    if detail is DetailLevel.FULL and not inventory_complete:
        raise ParameterValidationError(
            ["FULL requires a resolved authoritative inventory"]
        )
