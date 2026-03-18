#!/usr/bin/env python3
"""Sync SimpleCAD docs to a RAGFlow dataset with H2 chunking."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

try:
    from ragflow_sdk import RAGFlow  # type: ignore[import-not-found]
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit(
        "ragflow-sdk is required. Install with: pip install ragflow-sdk"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
STATE_VERSION = 1


@dataclass
class Chunk:
    content: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally sync docs/ into a RAGFlow dataset",
    )
    parser.add_argument("--base-url", default=os.getenv("RAGFLOW_BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("RAGFLOW_API_KEY"))
    parser.add_argument("--dataset-id", default=os.getenv("RAGFLOW_DATASET_ID"))
    parser.add_argument("--dataset-name", default=os.getenv("RAGFLOW_DATASET_NAME"))
    parser.add_argument("--create-dataset", action="store_true")
    parser.add_argument(
        "--embedding-model", default=os.getenv("RAGFLOW_EMBEDDING_MODEL")
    )
    parser.add_argument(
        "--permission",
        default=os.getenv("RAGFLOW_DATASET_PERMISSION", "me"),
    )
    parser.add_argument(
        "--description",
        default=os.getenv("RAGFLOW_DATASET_DESCRIPTION", ""),
    )
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR))
    parser.add_argument("--state-file", default="")
    parser.add_argument("--heading-level", type=int, default=2)
    parser.add_argument("--delete-removed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=1,
        help="Print progress every N documents (0 disables)",
    )
    return parser.parse_args()


def ensure_required(value: Optional[str], name: str) -> str:
    if not value:
        raise SystemExit(f"Missing required option: {name}")
    return value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_front_matter(text: str) -> tuple[Optional[str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            front = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return front, body
    return None, text


def trim_blank_lines(lines: List[str]) -> List[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def find_heading_indices(lines: List[str], level: int) -> List[int]:
    prefix = "#" * level + " "
    indices: List[int] = []
    in_code_block = False
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
        if in_code_block:
            continue
        if line.startswith(prefix):
            indices.append(idx)
    return indices


def find_title_line(lines: List[str]) -> tuple[Optional[str], Optional[int]]:
    in_code_block = False
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
        if in_code_block:
            continue
        if line.startswith("# "):
            return line, idx
    return None, None


def chunk_markdown(text: str, heading_level: int) -> List[Chunk]:
    _, body = split_front_matter(text)
    lines = body.splitlines()

    heading_indices = find_heading_indices(lines, heading_level)
    title_line, title_index = find_title_line(lines)

    if not heading_indices:
        trimmed = "\n".join(trim_blank_lines(lines)).rstrip()
        if not trimmed:
            return []
        return [Chunk(content=trimmed + "\n")]

    first_heading = heading_indices[0]
    preamble_lines = lines[:first_heading]
    if title_index is not None and title_index < first_heading:
        preamble_lines = [
            line for idx, line in enumerate(preamble_lines) if idx != title_index
        ]
    preamble_lines = trim_blank_lines(preamble_lines)

    chunks: List[Chunk] = []
    for section_index, start in enumerate(heading_indices):
        end = (
            heading_indices[section_index + 1]
            if section_index + 1 < len(heading_indices)
            else len(lines)
        )
        section_lines = trim_blank_lines(lines[start:end])

        chunk_lines: List[str] = []
        if title_line:
            chunk_lines.append(title_line)
            chunk_lines.append("")
        if section_index == 0 and preamble_lines:
            chunk_lines.extend(preamble_lines)
            chunk_lines.append("")
        chunk_lines.extend(section_lines)

        chunk_text = "\n".join(chunk_lines).rstrip()
        if chunk_text:
            chunks.append(Chunk(content=chunk_text + "\n"))

    return chunks


def list_markdown_files(docs_dir: Path) -> List[Path]:
    return sorted([path for path in docs_dir.rglob("*.md") if path.is_file()])


def load_state(path: Path) -> dict:
    if not path.exists():
        return {
            "version": STATE_VERSION,
            "dataset_id": "",
            "docs_dir": "",
            "chunking": "",
            "files": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def list_all_documents(dataset: Any) -> List[Any]:
    docs: List[Any] = []
    page = 1
    page_size = 100
    while True:
        batch = dataset.list_documents(page=page, page_size=page_size)
        if not batch:
            break
        docs.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return docs


def delete_all_chunks(doc: Any, batch_size: int = 200) -> int:
    try:
        doc.delete_chunks(delete_all=True)
        return 0
    except TypeError:
        pass

    chunk_ids: List[str] = []
    page = 1
    page_size = 100
    while True:
        chunks = doc.list_chunks(page=page, page_size=page_size)
        if not chunks:
            break
        for chunk in chunks:
            chunk_id = getattr(chunk, "id", "")
            if chunk_id:
                chunk_ids.append(chunk_id)
        if len(chunks) < page_size:
            break
        page += 1

    if not chunk_ids:
        return 0

    deleted = 0
    for index in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[index : index + batch_size]
        try:
            doc.delete_chunks(ids=batch)
        except TypeError:
            doc.delete_chunks(batch)
        deleted += len(batch)
    return deleted


def get_display_name(path: Path, docs_dir: Path) -> str:
    return path.relative_to(docs_dir).as_posix()


def resolve_state_path(state_file: str, dataset_id: str) -> Path:
    if state_file:
        return Path(state_file).resolve()
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / f"ragflow_sync_state_{dataset_id}.json"


def main() -> None:
    args = parse_args()
    base_url = ensure_required(args.base_url, "--base-url or RAGFLOW_BASE_URL")
    api_key = ensure_required(args.api_key, "--api-key or RAGFLOW_API_KEY")
    dataset_id = args.dataset_id or ""
    dataset_name = args.dataset_name or ""
    if not dataset_id and not dataset_name:
        raise SystemExit(
            "Provide --dataset-id / RAGFLOW_DATASET_ID or "
            "--dataset-name / RAGFLOW_DATASET_NAME"
        )

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.exists():
        raise SystemExit(f"Docs directory not found: {docs_dir}")

    heading_level = args.heading_level
    if heading_level < 2:
        raise SystemExit("heading-level must be >= 2")

    chunking_id = f"h{heading_level}-v1"
    rag = RAGFlow(api_key=api_key, base_url=base_url)
    datasets = rag.list_datasets(id=dataset_id) if dataset_id else []
    if not datasets and dataset_name:
        datasets = rag.list_datasets(name=dataset_name)
    if not datasets and args.create_dataset and dataset_name:
        if args.dry_run:
            print(f"[dry-run] create dataset {dataset_name}")
            return
        create_kwargs = {
            "name": dataset_name,
            "permission": args.permission,
            "chunk_method": "manual",
        }
        if args.embedding_model:
            create_kwargs["embedding_model"] = args.embedding_model
        if args.description:
            create_kwargs["description"] = args.description
        datasets = [rag.create_dataset(**create_kwargs)]
    if not datasets:
        raise SystemExit(
            f"Dataset not found. id={dataset_id or 'N/A'} name={dataset_name or 'N/A'}"
        )
    if len(datasets) > 1 and not dataset_id:
        raise SystemExit(
            f"Multiple datasets matched name '{dataset_name}'. "
            "Provide --dataset-id instead."
        )
    dataset = datasets[0]
    dataset_id = dataset.id

    state_path = resolve_state_path(args.state_file, dataset_id)
    state = load_state(state_path)
    if state.get("version") != STATE_VERSION:
        print("State file version mismatch; full resync will be performed.")
        state["files"] = {}

    if state.get("dataset_id") and state.get("dataset_id") != dataset_id:
        print("Dataset changed; full resync will be performed.")
        state["files"] = {}

    if state.get("chunking") != chunking_id:
        print("Chunking strategy changed; full resync will be performed.")
        state["files"] = {}

    existing_docs = {doc.name: doc for doc in list_all_documents(dataset)}

    local_files = list_markdown_files(docs_dir)
    local_map = {get_display_name(path, docs_dir): path for path in local_files}
    total_docs = len(local_map)
    if total_docs == 0:
        print(f"No markdown files found under {docs_dir}")
        return
    print(f"Syncing {total_docs} documents from {docs_dir}")

    updated = 0
    created = 0
    skipped = 0
    errors: List[str] = []

    for index, (display_name, path) in enumerate(local_map.items(), start=1):
        text = read_text(path)
        digest = sha256_text(text)
        entry = state.get("files", {}).get(display_name, {})
        if entry.get("sha256") == digest:
            skipped += 1
            if args.progress_interval and index % args.progress_interval == 0:
                print(f"[{index}/{total_docs}] skipped {display_name}")
            continue

        chunks = chunk_markdown(text, heading_level)
        if not chunks:
            print(f"Skipping empty doc: {display_name}")
            skipped += 1
            continue

        doc = existing_docs.get(display_name)
        if doc is None and entry.get("doc_id"):
            doc = next(
                (
                    item
                    for item in existing_docs.values()
                    if item.id == entry.get("doc_id")
                ),
                None,
            )

        try:
            action = "updated"
            if doc is None:
                action = "created"
                if args.dry_run:
                    print(f"[dry-run] create {display_name}")
                else:
                    uploaded = dataset.upload_documents(
                        [
                            {
                                "display_name": display_name,
                                "blob": text.encode("utf-8"),
                            }
                        ]
                    )
                    if uploaded:
                        doc = uploaded[0]
                    else:
                        candidates = dataset.list_documents(keywords=display_name)
                        doc = next(
                            (item for item in candidates if item.name == display_name),
                            None,
                        )
                created += 1
            else:
                if args.dry_run:
                    print(f"[dry-run] update {display_name}")
                updated += 1

            if doc is None:
                raise RuntimeError("Unable to resolve document after upload")

            title_line, _ = find_title_line(text.splitlines())
            title = title_line[2:].strip() if title_line else path.stem
            if not args.dry_run:
                doc.update(
                    {
                        "chunk_method": "manual",
                        "meta_fields": {
                            "source_path": display_name,
                            "sha256": digest,
                            "title": title,
                            "chunking": chunking_id,
                        },
                    }
                )
                delete_all_chunks(doc)
                for chunk in chunks:
                    doc.add_chunk(content=chunk.content)

            if args.progress_interval and index % args.progress_interval == 0:
                print(
                    f"[{index}/{total_docs}] {action} {display_name} "
                    f"(chunks={len(chunks)})"
                )

            state.setdefault("files", {})[display_name] = {
                "doc_id": doc.id,
                "sha256": digest,
                "title": title,
            }

        except Exception as exc:  # noqa: BLE001
            errors.append(f"{display_name}: {exc}")
            if args.progress_interval and index % args.progress_interval == 0:
                print(f"[{index}/{total_docs}] error {display_name}: {exc}")

    removed = 0
    if args.delete_removed:
        removed_doc_ids: List[str] = []
        for display_name, entry in list(state.get("files", {}).items()):
            if display_name in local_map:
                continue
            doc_id = entry.get("doc_id")
            if not doc_id:
                continue
            removed += 1
            removed_doc_ids.append(doc_id)
            if not args.dry_run:
                state["files"].pop(display_name, None)
        if removed_doc_ids:
            if args.dry_run:
                print(f"[dry-run] delete {len(removed_doc_ids)} docs")
            else:
                dataset.delete_documents(ids=removed_doc_ids)

    state.update(
        {
            "version": STATE_VERSION,
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "docs_dir": str(docs_dir),
            "chunking": chunking_id,
        }
    )

    if not args.dry_run:
        save_state(state_path, state)

    print(
        "Sync complete. "
        f"created={created}, updated={updated}, skipped={skipped}, removed={removed}."
    )

    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
