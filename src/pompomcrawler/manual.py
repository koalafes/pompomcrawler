from __future__ import annotations

import csv
from pathlib import Path

from .models import RawDocument, now_iso


def import_manual_csv(path: Path) -> list[RawDocument]:
    docs: list[RawDocument] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = (row.get("title") or "").strip()
            url = (row.get("source_url") or row.get("url") or "").strip()
            source_name = (row.get("source_name") or "manual").strip()
            notes = (row.get("notes") or "").strip()
            text = "\n".join(
                value
                for value in [
                    title,
                    row.get("kind", ""),
                    row.get("date", ""),
                    row.get("start_date", ""),
                    row.get("end_date", ""),
                    row.get("release_date", ""),
                    row.get("seller_or_venue", ""),
                    notes,
                ]
                if value
            )
            docs.append(
                RawDocument(
                    url=url or f"manual:{title}",
                    source_name=source_name,
                    title=title or url or "manual item",
                    text=text,
                    fetched_at=now_iso(),
                    notes=notes,
                )
            )
    return docs

