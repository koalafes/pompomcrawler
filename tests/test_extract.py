from pompomcrawler.extract import (
    OpenAIExtractor,
    extract_items_from_documents,
    guess_first_japanese_date,
    guess_japanese_date_ranges,
    heuristic_extract,
    load_dotenv_if_available,
    merge_duplicates,
)
from pompomcrawler.models import RawDocument, ScheduleItem


def test_load_dotenv_uses_global_env_for_missing_values(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    home = tmp_path / "home"
    global_env = home / ".config" / "pompomcrawler"
    workdir.mkdir()
    global_env.mkdir(parents=True)
    (workdir / ".env").write_text("OPENAI_MODEL=gpt-5.4-mini\n", encoding="utf-8")
    (global_env / ".env").write_text("OPENAI_MODEL=gpt-5.5\nOPENAI_API_KEY=global-key\n", encoding="utf-8")
    monkeypatch.chdir(workdir)
    monkeypatch.setattr("pompomcrawler.extract.GLOBAL_ENV_PATH", global_env / ".env")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_dotenv_if_available()

    assert __import__("os").environ["OPENAI_MODEL"] == "gpt-5.4-mini"
    assert __import__("os").environ["OPENAI_API_KEY"] == "global-key"


def test_heuristic_extract_keeps_related_candidate():
    doc = RawDocument(
        url="https://example.com/news",
        source_name="sample",
        title="ポムポムプリン 新商品のお知らせ",
        text="ポムポムプリンの新商品を発売します。発売日は2026年6月1日です。",
        fetched_at="2026-05-23T00:00:00+00:00",
        image_url="https://example.com/pompompurin.jpg",
    )

    items = heuristic_extract(doc)

    assert len(items) == 1
    assert items[0].kind == "product"
    assert items[0].release_date == "2026-06-01"
    assert items[0].status == "needs_review"
    assert items[0].source_url == doc.url
    assert items[0].image_url == "https://example.com/pompompurin.jpg"


def test_extract_items_uses_heuristic_dates_when_openai_fails(monkeypatch):
    doc = RawDocument(
        url="https://example.com/news",
        source_name="sample",
        title="数量限定☆ポムポムプリンコラボデザインが登場！",
        text="2026/06/01 ポムポムプリン30周年を記念したコラボデザインが発売中です。",
        fetched_at="2026-06-03T00:00:00+00:00",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.setattr(OpenAIExtractor, "extract", lambda self, doc: (_ for _ in ()).throw(RuntimeError("boom")))

    items = extract_items_from_documents([doc], use_openai=True)

    assert items[0].release_date == "2026-06-01"
    assert "OpenAI extraction failed: boom" in items[0].review_reason


def test_heuristic_extract_uses_date_range_for_multi_city_pop_up():
    doc = RawDocument(
        url="https://example.com/popup",
        source_name="sample",
        title="ポムポムプリン30周年を記念したPOP-UP STOREを開催！（東京・京都）",
        text=(
            "開催期間 | 5月14日（木）～5月25日（月） "
            "開催期間 | 6月5日（金）～6月17日（水）"
        ),
        fetched_at="2026-06-03T00:00:00+00:00",
    )

    items = heuristic_extract(doc)

    assert items[0].kind == "event"
    assert items[0].start_date == "2026-05-14"
    assert items[0].end_date == "2026-06-17"


def test_guess_japanese_date_ranges_supports_slash_dates():
    ranges = guess_japanese_date_ranges("開催期間 2026/04/10 ～ 2026/12/31", default_year=2026)

    assert ranges == [("2026-04-10", "2026-12-31")]


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


def test_merge_duplicates_keeps_first_available_image():
    without_image = ScheduleItem(
        title="ポムポムプリン イベント",
        kind="event",
        start_date="2026-06-01",
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
    with_image = ScheduleItem(
        title="ポムポムプリンイベント",
        kind="event",
        start_date="2026-06-01",
        end_date="",
        release_date="",
        reservation_start="",
        seller_or_venue="",
        source_url="https://example.com/b",
        source_name="second",
        confidence=0.45,
        status="needs_review",
        review_reason="second pass",
        notes="",
        image_url="https://example.com/event.jpg",
    )

    merged = merge_duplicates([without_image, with_image])

    assert merged[0].image_url == "https://example.com/event.jpg"


def test_guess_first_japanese_date_uses_default_year_when_omitted():
    assert guess_first_japanese_date("6月1日（月）より予約開始", default_year=2026) == "2026-06-01"


def test_guess_first_japanese_date_supports_slash_date():
    assert guess_first_japanese_date("2026/06/01 ポムポムプリン発売中", default_year=2025) == "2026-06-01"
