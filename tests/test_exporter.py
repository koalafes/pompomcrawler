from pathlib import Path

from pompomcrawler.exporter import export_schedule
from pompomcrawler.html_calendar import export_calendar_html
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
    assert ".range-bar" not in html
    assert "function rangeSegments" not in html
    assert "function itemOccursOnCalendar" in html
    assert "return item.primaryDate === dayIso" in html
    assert "function itemOccursOn" in html
    assert "開催中の予定" in html
    assert "function appendMobileSelectedSection" in html
    assert "const newItem = items.find(isNewItem)" in html
    assert "mobile-selected-section-title" in html
    assert "function upcomingAgendaItems" in html
    assert "function nextKnownDate" in html
    assert "item.startDate <= today && today <= item.endDate" in html
    assert "function isNewItem" in html
    assert "new-badge" in html
    assert "24 * 60 * 60 * 1000" in html
    assert "function updateDataSummary" in html
    assert "最終データ更新" in html
    assert "function renderLoading" in html
    assert "skeleton-shimmer" in html
    assert "予定を読み込み中" in html
    assert "function renderLoadError" in html


def test_export_calendar_html_can_use_aws_runtime_without_embedded_items(tmp_path: Path):
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
    )

    html_path = export_calendar_html([item], tmp_path, aws_runtime=True, filename="index.html")
    html = html_path.read_text(encoding="utf-8")

    assert html_path.name == "index.html"
    assert "const FALLBACK_ITEMS = [];" in html
    assert "__POMPOM_API_BASE_URL__" in html
    assert "__POMPOM_NEW_LABEL_AFTER__" in html
    assert "https://example.com/event" not in html


def test_public_calendar_omits_admin_controls(tmp_path: Path):
    html_path = export_calendar_html([], tmp_path, aws_runtime=True, filename="index.html")
    html = html_path.read_text(encoding="utf-8")

    assert "const ADMIN_MODE = false;" in html
    assert 'id="loginButton"' not in html
    assert 'id="adminActionButton"' not in html
    assert "/admin/items" in html
    assert "ADMIN_MODE ? \"/admin/items\" : \"/items\"" in html


def test_admin_calendar_uses_admin_controls_and_redirect(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("POMPOM_COGNITO_REDIRECT_URI", "https://example.com/")
    monkeypatch.setenv("POMPOM_COGNITO_LOGOUT_URI", "https://example.com/")

    html_path = export_calendar_html([], tmp_path, aws_runtime=True, filename="admin.html", admin_mode=True)
    html = html_path.read_text(encoding="utf-8")

    assert "ポムポムプリン予定帳 管理" in html
    assert "const ADMIN_MODE = true;" in html
    assert 'id="loginButton"' in html
    assert 'id="adminActionButton"' in html
    assert "https://example.com/" in html
    assert "pompomLoginReturnPath" in html
    assert "/admin/items" in html
    assert "/restore" in html
