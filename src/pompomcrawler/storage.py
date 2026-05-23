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
    return append_jsonl(path, (doc.to_dict() for doc in docs))


def read_raw_documents(path: Path = RAW_PATH) -> list[RawDocument]:
    return [RawDocument.from_dict(row) for row in read_jsonl(path)]


def append_schedule_items(items: Iterable[ScheduleItem], path: Path = ITEMS_PATH) -> int:
    return append_jsonl(path, (item.to_dict() for item in items))


def write_schedule_items(items: Iterable[ScheduleItem], path: Path = ITEMS_PATH) -> int:
    ensure_parent(path)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def read_schedule_items(path: Path = ITEMS_PATH) -> list[ScheduleItem]:
    return [ScheduleItem.from_dict(row) for row in read_jsonl(path)]
