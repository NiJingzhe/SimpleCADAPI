"""Authoritative product identities and quantity maturity, independent of display detail."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


TOP_LEVEL_COMPONENT_IDS = (
    "a00_skeleton",
    "a10_main_frame",
    "a20_warp_supply",
    "a30_upper_bias_supply",
    "a31_lower_bias_supply",
    "a40_upper_guide_frame",
    "a41_lower_guide_frame",
    "a42_bias_index_drive",
    "a50_binder_system",
    "a60_filling_system",
    "a61_engaging_rods",
    "a70_open_reed",
    "a80_width_hooks",
    "a90_linear_takeup",
)


class QuantityStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    description: str
    quantity: int | None
    status: QuantityStatus
    source: str

    def __post_init__(self) -> None:
        if (
            not self.item_id.strip()
            or not self.description.strip()
            or not self.source.strip()
        ):
            raise ValueError(
                "inventory identity, description, and source must not be empty"
            )
        if self.status is QuantityStatus.RESOLVED:
            if self.quantity is None or self.quantity <= 0:
                raise ValueError("resolved inventory items require a positive quantity")
        elif self.quantity is not None:
            raise ValueError("unresolved inventory quantities must be None")


@dataclass(frozen=True)
class Inventory:
    items: tuple[InventoryItem, ...]

    def __post_init__(self) -> None:
        ids = tuple(item.item_id for item in self.items)
        if len(ids) != len(set(ids)):
            raise ValueError("inventory item IDs must be unique")

    @property
    def unresolved_ids(self) -> tuple[str, ...]:
        return tuple(
            item.item_id
            for item in self.items
            if item.status is QuantityStatus.UNRESOLVED
        )

    @property
    def complete(self) -> bool:
        return not self.unresolved_ids

    def require_complete(self) -> None:
        if self.unresolved_ids:
            raise ValueError(
                "unresolved inventory quantities: " + ", ".join(self.unresolved_ids)
            )


def default_inventory() -> Inventory:
    """Record known counts and preserve every material count gap as unresolved."""

    resolved = QuantityStatus.RESOLVED
    unresolved = QuantityStatus.UNRESOLVED
    return Inventory(
        items=(
            InventoryItem("A40", "upper guide frame", 1, resolved, "design/03:133-146"),
            InventoryItem("A41", "lower guide frame", 1, resolved, "design/03:133-146"),
            InventoryItem(
                "G-03", "upper replaceable wear rail", 2, resolved, "design/03:74-90"
            ),
            InventoryItem(
                "G-04", "lower replaceable wear rail", 2, resolved, "design/03:74-90"
            ),
            InventoryItem(
                "G-BLOCK", "bias-yarn guide block", None, unresolved, "GAP-02"
            ),
            InventoryItem(
                "W-END", "independent warp end module", None, unresolved, "GAP-14"
            ),
            InventoryItem(
                "B-04", "bias bobbin carrier station", None, unresolved, "GAP-02"
            ),
            InventoryItem("N-03", "binder needle", None, unresolved, "GAP-06"),
            InventoryItem(
                "R-07", "rapier hook head", 3, resolved, "design/04 filling system"
            ),
            InventoryItem(
                "D-02", "open reed blade", None, unresolved, "design/08 inventory gap"
            ),
            InventoryItem(
                "H-01", "left edge hook, per cycle", 1, resolved, "design/00:70"
            ),
            InventoryItem(
                "H-02", "right edge hook, per cycle", 1, resolved, "design/00:70"
            ),
            InventoryItem(
                "T-01/T-02", "take-up linear rails", 2, resolved, "design/05"
            ),
            InventoryItem("T-03/T-04", "take-up ball screws", 2, resolved, "design/05"),
            InventoryItem(
                "FASTENER", "machine fasteners", None, unresolved, "design/10:300"
            ),
            InventoryItem(
                "SPARE", "production spares", None, unresolved, "design/10:300"
            ),
        )
    )
