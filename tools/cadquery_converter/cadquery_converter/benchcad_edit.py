"""Load BenchCAD edit-bench rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional


@dataclass
class BenchCADEditRow:
    record_id: str
    family: str
    edit_type: str
    category: str
    category_label: str
    instruction: str
    orig_code: str
    gt_code: str
    iou: Optional[float] = None
    pos_id: int = 0


def _iter_edit_parquet_paths(dataset_root: Path) -> List[Path]:
    data_dir = dataset_root / "edit-bench" / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"BenchCAD edit-bench/data not found under {dataset_root}")
    return sorted(data_dir.glob("edit_bench-*.parquet"))


def iter_benchcad_edit_rows(
    dataset_root: str | Path,
    *,
    limit: Optional[int] = None,
) -> Iterator[BenchCADEditRow]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("BenchCAD edit loading requires pyarrow: uv pip install pyarrow") from exc

    count = 0
    for parquet_path in _iter_edit_parquet_paths(Path(dataset_root)):
        table = pq.read_table(parquet_path)
        for row_index in range(table.num_rows):
            iou_val = table["iou"][row_index].as_py() if "iou" in table.column_names else None
            yield BenchCADEditRow(
                record_id=str(table["record_id"][row_index].as_py()),
                family=str(table["family"][row_index].as_py() if "family" in table.column_names else ""),
                edit_type=str(table["edit_type"][row_index].as_py() if "edit_type" in table.column_names else ""),
                category=str(table["category"][row_index].as_py() if "category" in table.column_names else ""),
                category_label=str(
                    table["category_label"][row_index].as_py() if "category_label" in table.column_names else ""
                ),
                instruction=str(table["instruction"][row_index].as_py()),
                orig_code=str(table["orig_code"][row_index].as_py()),
                gt_code=str(table["gt_code"][row_index].as_py()),
                iou=float(iou_val) if iou_val is not None else None,
                pos_id=int(table["pos_id"][row_index].as_py() if "pos_id" in table.column_names else 0),
            )
            count += 1
            if limit is not None and count >= limit:
                return
