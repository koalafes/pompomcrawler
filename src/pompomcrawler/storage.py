from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, TypeVar

from .models import RawDocument, ScheduleItem

T = TypeVar("T")


DATA_DIR = Path("data")
RAW_PATH = DATA_DIR / "raw_documents.jsonl"
ITEMS_PATH = DATA_DIR / "schedule_items.jsonl"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, rows: Iterable[dict]) -> int:
    ensure_parent(path)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    ensure_parent(path)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_raw_documents(docs: Iterable[RawDocument], path: Path = RAW_PATH) -> int:
    incoming = list(docs)
    if not incoming:
        return 0

    existing = read_raw_documents(path)
    index_by_url = {document_key(doc): index for index, doc in enumerate(existing) if document_key(doc)}
    changed = 0

    for doc in incoming:
        key = document_key(doc)
        if not key or key not in index_by_url:
            index_by_url[key] = len(existing) if key else -1
            existing.append(doc)
            changed += 1
            continue

        current = existing[index_by_url[key]]
        if raw_document_content(current) == raw_document_content(doc):
            continue
        existing[index_by_url[key]] = doc
        changed += 1

    if changed:
        write_raw_documents(existing, path)
    return changed


def read_raw_documents(path: Path = RAW_PATH) -> list[RawDocument]:
    return [RawDocument.from_dict(row) for row in read_jsonl(path)]


def append_schedule_items(items: Iterable[ScheduleItem], path: Path = ITEMS_PATH) -> int:
    incoming = list(items)
    if not incoming:
        return 0

    from .extract import merge_duplicates

    existing = read_schedule_items(path)
    existing_rows = [item.to_dict() for item in existing]
    merged = merge_duplicates([*existing, *incoming])
    if len(merged) != len(existing) or [item.to_dict() for item in merged] != existing_rows:
        write_schedule_items(merged, path)
    return max(0, len(merged) - len(existing))


def write_raw_documents(docs: Iterable[RawDocument], path: Path = RAW_PATH) -> int:
    return write_jsonl(path, (doc.to_dict() for doc in docs))


def write_schedule_items(items: Iterable[ScheduleItem], path: Path = ITEMS_PATH) -> int:
    return write_jsonl(path, (item.to_dict() for item in items))


def read_schedule_items(path: Path = ITEMS_PATH) -> list[ScheduleItem]:
    return [ScheduleItem.from_dict(row) for row in read_jsonl(path)]


def document_key(doc: RawDocument) -> str:
    return doc.url.strip()


def raw_document_content(doc: RawDocument) -> dict:
    data = doc.to_dict()
    data.pop("fetched_at", None)
    return data


def split_source_urls(value: str) -> set[str]:
    return {url.strip() for url in value.split(" | ") if url.strip()}


def schedule_source_urls(items: Iterable[ScheduleItem]) -> set[str]:
    urls: set[str] = set()
    for item in items:
        urls.update(split_source_urls(item.source_url))
    return urls
