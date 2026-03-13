from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


_TAG_SEGMENT = r"[a-z][a-z0-9_-]*"
_TAG_RE = re.compile(rf"^{_TAG_SEGMENT}(?:\.{_TAG_SEGMENT})*$")


def is_normalized_tag(tag: str) -> bool:
    """检查标签是否符合规范格式。

    Args:
        tag: 标签字符串。

    Returns:
        bool: 是否符合规范。
    """
    if not isinstance(tag, str):
        return False
    return bool(_TAG_RE.fullmatch(tag))


def normalize_tag(tag: str, *, strict: bool = True) -> str:
    """规范化标签。

    Args:
        tag: 原始标签。
        strict: 是否严格校验，True 时只接受已规范化格式。

    Returns:
        str: 规范化后的标签。

    Raises:
        TypeError: tag 不是字符串。
        ValueError: 规范化失败。
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
    """标签传播策略。"""

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
        """判断标签是否应该向下传播。

        Args:
            tag: 标签字符串。

        Returns:
            bool: 是否传播。
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
    """生成锚点标签的候选列表。

    Args:
        tag: 用户输入标签。

    Returns:
        List[str]: 候选标签列表，按优先级排序。
    """
    token = tag.strip().lower()
    if not token:
        return []

    if is_normalized_tag(token) and "." in token:
        candidates = [token]
        for prefix in ("role.", "anchor.", "face.", "legacy."):
            if token.startswith(prefix):
                candidates.append(token[len(prefix) :])
        return candidates

    return [
        f"role.{token}",
        f"anchor.{token}",
        f"face.{token}",
        f"legacy.{token}",
        token,
    ]
