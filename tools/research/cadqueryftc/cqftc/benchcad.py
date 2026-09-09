"""Load BenchCAD HuggingFace parquet shards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional


@dataclass
class BenchCADRow:
    stem: str
    family: str
    variant: str
    difficulty: str
    base_plane: str
    standard: str
    code: str


def _iter_parquet_paths(dataset_root: Path) -> List[Path]:
    data_dir = dataset_root / "code_gen" / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"BenchCAD code_gen/data not found under {dataset_root}")
    return sorted(data_dir.glob("code_gen-*.parquet"))


def iter_benchcad_rows(
    dataset_root: str | Path,
    *,
    limit: Optional[int] = None,
) -> Iterator[BenchCADRow]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("BenchCAD loading requires pyarrow: uv pip install pyarrow") from exc

    count = 0
    for parquet_path in _iter_parquet_paths(Path(dataset_root)):
        table = pq.read_table(
            parquet_path,
            columns=[
                "stem",
                "family",
                "variant",
                "difficulty",
                "base_plane",
                "standard",
                "code",
            ],
        )
        for row_index in range(table.num_rows):
            yield BenchCADRow(
                stem=str(table["stem"][row_index].as_py()),
                family=str(table["family"][row_index].as_py()),
                variant=str(table["variant"][row_index].as_py()),
                difficulty=str(table["difficulty"][row_index].as_py()),
                base_plane=str(table["base_plane"][row_index].as_py()),
                standard=str(table["standard"][row_index].as_py() or ""),
                code=str(table["code"][row_index].as_py()),
            )
            count += 1
            if limit is not None and count >= limit:
                return
