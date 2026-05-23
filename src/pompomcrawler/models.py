from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


SCHEDULE_COLUMNS = [
    "title",
    "kind",
    "start_date",
    "end_date",
    "release_date",
    "reservation_start",
    "seller_or_venue",
    "source_url",
    "image_url",
    "source_name",
    "confidence",
    "status",
    "review_reason",
    "notes",
]

VALID_STATUSES = {"candidate", "needs_review", "confirmed", "excluded"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class RawDocument:
    url: str
    source_name: str
    title: str
    text: str
    fetched_at: str
    notes: str = ""
    image_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawDocument":
        return cls(
            url=str(data.get("url", "")),
            source_name=str(data.get("source_name", "")),
            title=str(data.get("title", "")),
            text=str(data.get("text", "")),
            fetched_at=str(data.get("fetched_at", "")),
            notes=str(data.get("notes", "")),
            image_url=str(data.get("image_url", "")),
        )


@dataclass(slots=True)
class ScheduleItem:
    title: str
    kind: str
    start_date: str
    end_date: str
    release_date: str
    reservation_start: str
    seller_or_venue: str
    source_url: str
    source_name: str
    confidence: float
    status: str
    review_reason: str
    notes: str
    image_url: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            self.status = "needs_review"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {column: data.get(column, "") for column in SCHEDULE_COLUMNS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleItem":
        return cls(
            title=str(data.get("title", "")),
            kind=str(data.get("kind", "")),
            start_date=str(data.get("start_date", "")),
            end_date=str(data.get("end_date", "")),
            release_date=str(data.get("release_date", "")),
            reservation_start=str(data.get("reservation_start", "")),
            seller_or_venue=str(data.get("seller_or_venue", "")),
            source_url=str(data.get("source_url", "")),
            source_name=str(data.get("source_name", "")),
            confidence=float(data.get("confidence") or 0.0),
            status=str(data.get("status", "needs_review")),
            review_reason=str(data.get("review_reason", "")),
            notes=str(data.get("notes", "")),
            image_url=str(data.get("image_url", "")),
        )
