from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional


Predicate = Callable[[Any], bool]
KeyFn = Callable[[Any], Any]


def _get_tags(obj: Any) -> List[str]:
    """读取对象上的标签列表。

    Args:
        obj: 任意对象，优先读取 get_tags()，其次读取 _tags。

    Returns:
        List[str]: 标签列表，未找到则返回空列表。
    """
    if hasattr(obj, "get_tags"):
        try:
            return list(obj.get_tags())
        except Exception:
            return []
    tags = getattr(obj, "_tags", None)
    if tags is None:
        return []
    return list(tags)


def _get_metadata_root(obj: Any) -> dict:
    """读取对象的元数据字典。

    Args:
        obj: 任意对象，优先读取 _metadata。

    Returns:
        dict: 元数据根字典，未找到则返回空字典。
    """
    root = getattr(obj, "_metadata", None)
    if isinstance(root, dict):
        return root
    return {}


def _lookup_metadata(obj: Any, path: str) -> Any:
    """按点路径读取对象元数据。

    Args:
        obj: 任意对象。
        path: 点分隔路径，例如 "geo.type"。

    Returns:
        Any: 命中值，未命中返回 None。
    """
    if not isinstance(path, str) or not path:
        return None
    segments = path.split(".")
    current: Any = _get_metadata_root(obj)
    for seg in segments:
        if isinstance(current, dict) and seg in current:
            current = current[seg]
        else:
            return None
    return current


def tag(pattern: str) -> Predicate:
    """构造基于标签的谓词。

    Args:
        pattern: 标签匹配模式，支持后缀通配符 "*"。

    Returns:
        Callable[[Any], bool]: 谓词函数。

    Raises:
        TypeError: pattern 不是字符串。
        ValueError: 通配符位置不合法。

    Usage:
        Q.tag("face.top") 或 Q.tag("role.*")。

    Examples:
        pred = Q.tag("role.*")
        matched = pred(obj)
    """
    if not isinstance(pattern, str):
        raise TypeError("pattern must be a string")

    pattern = pattern.strip()
    if "*" in pattern and not pattern.endswith("*"):
        raise ValueError("only trailing '*' wildcard is supported")

    if pattern.endswith("*"):
        prefix = pattern[:-1]

        def _predicate(obj: Any) -> bool:
            return any(tag.startswith(prefix) for tag in _get_tags(obj))

        return _predicate

    def _predicate(obj: Any) -> bool:
        return pattern in _get_tags(obj)

    return _predicate


def meta(path: str, op: str, value: Any) -> Predicate:
    """构造基于元数据的谓词。

    Args:
        path: 元数据路径，例如 "geo.type"。
        op: 比较操作符，支持 == != > >= < <= 。
        value: 比较目标值。

    Returns:
        Callable[[Any], bool]: 谓词函数。

    Raises:
        TypeError: op 不是字符串。
        ValueError: 操作符不支持。

    Usage:
        Q.meta("geo.type", "==", "box")

    Examples:
        pred = Q.meta("geo.size.x", ">", 1.0)
        matched = pred(obj)
    """
    if not isinstance(op, str):
        raise TypeError("op must be a string")

    op = op.strip()

    def _predicate(obj: Any) -> bool:
        actual = _lookup_metadata(obj, path)
        if op == "==":
            return actual == value
        if op == "!=":
            return actual != value
        if actual is None:
            return False
        try:
            if op == ">":
                return actual > value
            if op == ">=":
                return actual >= value
            if op == "<":
                return actual < value
            if op == "<=":
                return actual <= value
        except Exception:
            return False
        raise ValueError(f"unsupported op: {op}")

    return _predicate


def value(path: str, default: Any = None) -> KeyFn:
    """构造取值函数，用于排序或投影。

    Args:
        path: 元数据路径，例如 "geo.height"。
        default: 取值失败时的默认值。

    Returns:
        Callable[[Any], Any]: 取值函数。

    Usage:
        Q.select(items).order_by(Q.value("geo.height"))

    Examples:
        key = Q.value("geo.height", 0.0)
        height = key(obj)
    """

    def _getter(obj: Any) -> Any:
        actual = _lookup_metadata(obj, path)
        if actual is not None:
            return actual

        if path.startswith("geo."):
            remainder = path.split(".", 1)[1]
            if "." not in remainder:
                if remainder == "area" and hasattr(obj, "get_area"):
                    try:
                        return obj.get_area()
                    except Exception:
                        return default
                if remainder == "length" and hasattr(obj, "get_length"):
                    try:
                        return obj.get_length()
                    except Exception:
                        return default
                if remainder == "volume" and hasattr(obj, "get_volume"):
                    try:
                        return obj.get_volume()
                    except Exception:
                        return default
        return default

    return _getter


def geo(field: str, default: Any = None) -> KeyFn:
    """快捷构造 geo 元数据取值函数。

    Args:
        field: geo 字段名，如 "type"、"height"。
        default: 取值失败时的默认值。

    Returns:
        Callable[[Any], Any]: 取值函数。

    Usage:
        Q.select(items).order_by(Q.geo("height"))
    """
    return value(f"geo.{field}", default)


def and_(*predicates: Predicate) -> Predicate:
    """构造 AND 组合谓词。

    Args:
        *predicates: 任意数量谓词。

    Returns:
        Callable[[Any], bool]: 组合谓词。

    Usage:
        Q.and_(Q.tag("face.top"), Q.tag("role.mounting_surface"))
    """

    def _predicate(obj: Any) -> bool:
        for pred in predicates:
            if not pred(obj):
                return False
        return True

    return _predicate


def or_(*predicates: Predicate) -> Predicate:
    """构造 OR 组合谓词。

    Args:
        *predicates: 任意数量谓词。

    Returns:
        Callable[[Any], bool]: 组合谓词。

    Usage:
        Q.or_(Q.tag("face.top"), Q.tag("face.bottom"))
    """

    def _predicate(obj: Any) -> bool:
        for pred in predicates:
            if pred(obj):
                return True
        return False

    return _predicate


def not_(predicate: Predicate) -> Predicate:
    """构造 NOT 谓词。

    Args:
        predicate: 单个谓词。

    Returns:
        Callable[[Any], bool]: 取反谓词。

    Usage:
        Q.not_(Q.tag("state.*"))
    """

    def _predicate(obj: Any) -> bool:
        return not predicate(obj)

    return _predicate


class Query:
    def __init__(self, items: Iterable[Any]):
        """创建查询对象。

        Args:
            items: 任意可迭代对象。
        """
        self._items = list(items)

    def where(self, predicate: Predicate) -> "Query":
        """根据谓词过滤对象。

        Args:
            predicate: 过滤谓词。

        Returns:
            Query: 新查询对象。
        """
        return Query([item for item in self._items if predicate(item)])

    def order_by(self, key: KeyFn, desc: bool = False) -> "Query":
        """按 key 排序。

        Args:
            key: 取值函数。
            desc: 是否降序。

        Returns:
            Query: 新查询对象。
        """

        def _safe_key(obj: Any):
            value = key(obj)
            return (value is None, value)

        return Query(sorted(self._items, key=_safe_key, reverse=desc))

    def limit(self, count: int) -> "Query":
        """限制返回数量。

        Args:
            count: 最大数量。

        Returns:
            Query: 新查询对象。
        """
        if count <= 0:
            return Query([])
        return Query(self._items[:count])

    def first(self) -> Optional[Any]:
        """返回首个元素。

        Returns:
            Optional[Any]: 首元素或 None。
        """
        return self._items[0] if self._items else None

    def all(self) -> List[Any]:
        """返回全部结果。

        Returns:
            List[Any]: 结果列表。
        """
        return list(self._items)


def select(items: Iterable[Any]) -> Query:
    """创建查询对象。

    Args:
        items: 任意可迭代对象。

    Returns:
        Query: 查询对象。

    Usage:
        Q.select(items).where(Q.tag("face.top")).first()
    """
    return Query(items)
