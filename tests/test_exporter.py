from pathlib import Path

from pompomcrawler.exporter import export_schedule
from pompomcrawler.models import ScheduleItem


def test_export_schedule_writes_csv(tmp_path: Path):
    item = ScheduleItem(
        title="ポムポムプリン イベント",
        kind="event",
        start_date="2026-06-01",
        end_date="2026-06-30",
        release_date="",
        reservation_start="",
        seller_or_venue="東京",
        source_url="https://example.com/event",
        source_name="manual",
        confidence=0.9,
        status="needs_review",
        review_reason="sample",
        notes="",
        image_url="https://example.com/event.jpg",
    )

    csv_path, xlsx_path, html_path = export_schedule([item], tmp_path)

    assert csv_path.exists()
    assert xlsx_path is None or xlsx_path.exists()
    assert html_path.exists()
    assert "ポムポムプリン イベント" in csv_path.read_text(encoding="utf-8-sig")
    html = html_path.read_text(encoding="utf-8")
    assert "ポムポムプリン予定帳" in html
    assert "https://example.com/event.jpg" in html
