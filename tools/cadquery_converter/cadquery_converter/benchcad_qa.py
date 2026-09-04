"""Load BenchCAD QA rows (parquet + optional TSV)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, List, Optional, Union


@dataclass
class BenchCADQARow:
    stem: str
    family: str
    question: str
    answer: Any
    qa_type: str
    level: str
    gt_code: str
    qa_id: str = ""
    standard: str = ""
    image: Optional[Any] = None


def _parse_qa_field(raw: Any) -> tuple[str, Any, str]:
    if isinstance(raw, dict):
        return (
            str(raw.get("question") or ""),
            raw.get("answer"),
            str(raw.get("type") or raw.get("qa_type") or ""),
        )
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw, "", ""
        if isinstance(payload, dict):
            return (
                str(payload.get("question") or ""),
                payload.get("answer"),
                str(payload.get("type") or payload.get("qa_type") or ""),
            )
    return "", "", ""


def _iter_qa_parquet_paths(dataset_root: Path) -> List[Path]:
    candidates = [
        dataset_root / "QA" / "qa_2400.parquet",
        dataset_root / "qa_2400.parquet",
    ]
    return [path for path in candidates if path.is_file()]


def iter_benchcad_qa_rows(
    dataset_root: str | Path,
    *,
    limit: Optional[int] = None,
) -> Iterator[BenchCADQARow]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("BenchCAD QA loading requires pyarrow: uv pip install pyarrow") from exc

    root = Path(dataset_root)
    paths = _iter_qa_parquet_paths(root)
    if not paths:
        # Fallback: TSV without images
        tsv = root / "vlmevalkit" / "BenchCAD_QA.tsv"
        if not tsv.is_file():
            raise FileNotFoundError(f"BenchCAD QA parquet/TSV not found under {root}")
        yield from _iter_qa_tsv(tsv, limit=limit)
        return

    count = 0
    for parquet_path in paths:
        table = pq.read_table(parquet_path)
        for row_index in range(table.num_rows):
            qa_raw = table["qa"][row_index].as_py() if "qa" in table.column_names else ""
            question, answer, qa_type = _parse_qa_field(qa_raw)
            image = None
            if "composite_png" in table.column_names:
                image = table["composite_png"][row_index].as_py()
            yield BenchCADQARow(
                stem=str(table["stem"][row_index].as_py()),
                family=str(table["family"][row_index].as_py() if "family" in table.column_names else ""),
                question=question,
                answer=answer,
                qa_type=qa_type,
                level=str(table["qa_level"][row_index].as_py() if "qa_level" in table.column_names else ""),
                gt_code=str(table["gt_code"][row_index].as_py()),
                qa_id=str(table["qa_id"][row_index].as_py() if "qa_id" in table.column_names else ""),
                standard=str(table["standard"][row_index].as_py() if "standard" in table.column_names else ""),
                image=image,
            )
            count += 1
            if limit is not None and count >= limit:
                return


def _iter_qa_tsv(tsv_path: Path, *, limit: Optional[int] = None) -> Iterator[BenchCADQARow]:
    import csv

    count = 0
    with tsv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            yield BenchCADQARow(
                stem=str(row.get("stem") or ""),
                family=str(row.get("family") or ""),
                question=str(row.get("question") or ""),
                answer=row.get("answer"),
                qa_type=str(row.get("qa_type") or ""),
                level=str(row.get("level") or ""),
                gt_code=str(row.get("gt_code") or ""),
                standard=str(row.get("standard") or ""),
            )
            count += 1
            if limit is not None and count >= limit:
                return
