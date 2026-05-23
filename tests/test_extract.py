from pompomcrawler.extract import guess_first_japanese_date, heuristic_extract, merge_duplicates
from pompomcrawler.models import RawDocument, ScheduleItem


def test_heuristic_extract_keeps_related_candidate():
    doc = RawDocument(
        url="https://example.com/news",
        source_name="sample",
        title="ポムポムプリン 新商品のお知らせ",
        text="ポムポムプリンの新商品を発売します。発売日は2026年6月1日です。",
        fetched_at="2026-05-23T00:00:00+00:00",
    )

    items = heuristic_extract(doc)

    assert len(items) == 1
    assert items[0].kind == "product"
    assert items[0].release_date == "2026-06-01"
    assert items[0].status == "needs_review"
    assert items[0].source_url == doc.url


def test_heuristic_extract_excludes_unrelated_text():
    doc = RawDocument(
        url="https://example.com/news",
        source_name="sample",
        title="別キャラクターのニュース",
        text="シナモロールのイベントです。",
        fetched_at="2026-05-23T00:00:00+00:00",
    )

    items = heuristic_extract(doc)

    assert items[0].status == "excluded"


def test_merge_duplicates_combines_sources():
    first = ScheduleItem(
        title="ポムポムプリン 30周年グッズ",
        kind="product",
        start_date="",
        end_date="",
        release_date="2026-06-01",
        reservation_start="",
        seller_or_venue="",
        source_url="https://example.com/a",
        source_name="official",
        confidence=0.8,
        status="needs_review",
        review_reason="official source",
        notes="",
    )
    second = ScheduleItem(
        title="ポムポムプリン30周年グッズ",
        kind="product",
        start_date="",
        end_date="",
        release_date="2026-06-01",
        reservation_start="",
        seller_or_venue="",
        source_url="https://example.com/b",
        source_name="press",
        confidence=0.7,
        status="needs_review",
        review_reason="press source",
        notes="",
    )

    merged = merge_duplicates([first, second])

    assert len(merged) == 1
    assert "https://example.com/a" in merged[0].source_url
    assert "https://example.com/b" in merged[0].source_url


def test_merge_duplicates_enriches_generic_kind():
    generic = ScheduleItem(
        title="ポムポムプリン 予約開始",
        kind="other",
        start_date="",
        end_date="",
        release_date="",
        reservation_start="",
        seller_or_venue="",
        source_url="https://example.com/a",
        source_name="first",
        confidence=0.2,
        status="needs_review",
        review_reason="first pass",
        notes="",
    )
    enriched = ScheduleItem(
        title="ポムポムプリン予約開始",
        kind="reservation",
        start_date="",
        end_date="",
        release_date="",
        reservation_start="2026-06-01",
        seller_or_venue="",
        source_url="https://example.com/b",
        source_name="second",
        confidence=0.45,
        status="needs_review",
        review_reason="second pass",
        notes="",
    )

    merged = merge_duplicates([generic, enriched])

    assert merged[0].kind == "reservation"
    assert merged[0].reservation_start == "2026-06-01"


def test_guess_first_japanese_date_uses_default_year_when_omitted():
    assert guess_first_japanese_date("6月1日（月）より予約開始", default_year=2026) == "2026-06-01"
