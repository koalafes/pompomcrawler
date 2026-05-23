from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from .models import ScheduleItem


DEFAULT_PAST_DAYS = 30


def filter_schedule_window(
    items: Iterable[ScheduleItem],
    *,
    today: date | None = None,
    past_days: int = DEFAULT_PAST_DAYS,
    include_undated: bool = True,
) -> list[ScheduleItem]:
    today = today or date.today()
    cutoff = today - timedelta(days=past_days)
    filtered: list[ScheduleItem] = []
    for item in items:
        dates = item_dates(item)
        if not dates:
            if include_undated:
                filtered.append(item)
            continue
        if item_overlaps_window(item, cutoff):
            filtered.append(item)
    return filtered


def item_overlaps_window(item: ScheduleItem, cutoff: date) -> bool:
    dates = item_dates(item)
    if not dates:
        return False
    start = parse_iso_date(item.start_date)
    end = parse_iso_date(item.end_date)
    if start and end:
        return end >= cutoff
    return max(dates) >= cutoff


def item_dates(item: ScheduleItem) -> list[date]:
    dates = [
        parse_iso_date(item.release_date),
        parse_iso_date(item.start_date),
        parse_iso_date(item.reservation_start),
        parse_iso_date(item.end_date),
    ]
    return [value for value in dates if value is not None]


def primary_date(item: ScheduleItem) -> str:
    for value in [item.release_date, item.start_date, item.reservation_start, item.end_date]:
        parsed = parse_iso_date(value)
        if parsed:
            return parsed.isoformat()
    return ""


def parse_iso_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None

