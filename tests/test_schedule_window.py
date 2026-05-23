from datetime import date

from pompomcrawler.models import ScheduleItem
from pompomcrawler.schedule_window import filter_schedule_window


def item(title: str, start_date: str = "", end_date: str = "", release_date: str = "") -> ScheduleItem:
    return ScheduleItem(
        title=title,
        kind="event",
        start_date=start_date,
        end_date=end_date,
        release_date=release_date,
        reservation_start="",
        seller_or_venue="",
        source_url=f"https://example.com/{title}",
        source_name="test",
        confidence=0.8,
        status="needs_review",
        review_reason="test",
        notes="",
    )


def test_filter_schedule_window_keeps_recent_future_and_undated():
    filtered = filter_schedule_window(
        [
            item("old", release_date="2026-03-01"),
            item("recent", release_date="2026-05-01"),
            item("future", release_date="2026-06-01"),
            item("undated"),
        ],
        today=date(2026, 5, 23),
        past_days=30,
    )

    assert [entry.title for entry in filtered] == ["recent", "future", "undated"]


def test_filter_schedule_window_keeps_ongoing_event_with_recent_end():
    filtered = filter_schedule_window(
        [item("ongoing", start_date="2026-03-01", end_date="2026-05-01")],
        today=date(2026, 5, 23),
        past_days=30,
    )

    assert len(filtered) == 1
