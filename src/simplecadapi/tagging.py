from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


_TAG_SEGMENT = r"[a-z][a-z0-9_-]*"
_TAG_RE = re.compile(rf"^{_TAG_SEGMENT}(?:\.{_TAG_SEGMENT})*$")


def is_normalized_tag(tag: str) -> bool:
    """Check whether a tag matches the normalized format.

    Args:
        tag: Tag string.

    Returns:
        bool: Whether the tag is valid.
    """
    if not isinstance(tag, str):
        return False
    return bool(_TAG_RE.fullmatch(tag))


def normalize_tag(tag: str, *, strict: bool = True) -> str:
    """Normalize a tag.

    Args:
        tag: Raw tag.
        strict: Whether to validate strictly. When True, only already-normalized
            tags are accepted.

    Returns:
        str: Normalized tag.

    Raises:
        TypeError: If tag is not a string.
        ValueError: If normalization fails.
    """
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
    """Tag propagation policy."""

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
        """Check whether a tag should propagate downward.

        Args:
            tag: Tag string.

        Returns:
            bool: Whether the tag should propagate.
        """
        if tag in self.block_exact:
            return False
        if any(tag.startswith(prefix) for prefix in self.block_prefixes):
            return False
        if tag in self.propagate_exact:
            return True
        if any(tag.startswith(prefix) for prefix in self.propagate_prefixes):
            return True
        return False


DEFAULT_TAG_POLICY = TagPolicy()


def resolve_anchor_tag_candidates(tag: str) -> List[str]:
    """Generate candidate tags for anchor lookup.

    Args:
        tag: User-provided tag.

    Returns:
        List[str]: Candidate tags ordered by priority.
    """
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
