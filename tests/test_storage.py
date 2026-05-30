from pathlib import Path

from pompomcrawler.models import RawDocument, ScheduleItem
from pompomcrawler.storage import (
    append_raw_documents,
    append_schedule_items,
    read_raw_documents,
    read_schedule_items,
    schedule_source_urls,
)


def raw_doc(url: str, title: str = "title", text: str = "text", fetched_at: str = "2026-05-23T00:00:00+00:00") -> RawDocument:
    return RawDocument(
        url=url,
        source_name="source",
        title=title,
        text=text,
        fetched_at=fetched_at,
    )


def schedule_item(
    url: str,
    *,
    title: str = "ポムポムプリン 30周年グッズ",
    status: str = "needs_review",
    seller_or_venue: str = "",
) -> ScheduleItem:
    return ScheduleItem(
        title=title,
        kind="product",
        start_date="",
        end_date="",
        release_date="2026-06-01",
        reservation_start="",
        seller_or_venue=seller_or_venue,
        source_url=url,
        source_name="source",
        confidence=0.8,
        status=status,
        review_reason="sample",
        notes="",
    )


def test_append_raw_documents_updates_same_url_instead_of_duplicating(tmp_path: Path):
    path = tmp_path / "raw_documents.jsonl"

    assert append_raw_documents([raw_doc("https://example.com/a")], path) == 1
    assert append_raw_documents([raw_doc("https://example.com/a", fetched_at="2026-05-24T00:00:00+00:00")], path) == 0
    assert append_raw_documents([raw_doc("https://example.com/a", text="updated")], path) == 1

    docs = read_raw_documents(path)
    assert len(docs) == 1
    assert docs[0].text == "updated"


def test_append_schedule_items_merges_duplicate_and_preserves_existing_status(tmp_path: Path):
    path = tmp_path / "schedule_items.jsonl"
    confirmed = schedule_item("https://example.com/a", status="confirmed")
    enriched = schedule_item("https://example.com/a", seller_or_venue="サンリオ")

    assert append_schedule_items([confirmed], path) == 1
    assert append_schedule_items([enriched], path) == 0

    items = read_schedule_items(path)
    assert len(items) == 1
    assert items[0].status == "confirmed"
    assert items[0].seller_or_venue == "サンリオ"


def test_schedule_source_urls_splits_merged_sources():
    items = [schedule_item("https://example.com/a | https://example.com/b")]

    assert schedule_source_urls(items) == {"https://example.com/a", "https://example.com/b"}
