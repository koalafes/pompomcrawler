from pompomcrawler.aggregation import display_group_key, is_noise_item, merge_related_items
from pompomcrawler.models import ScheduleItem


def schedule_item(
    title: str,
    *,
    kind: str = "product",
    url: str = "https://example.com/news",
    start_date: str = "",
    end_date: str = "",
    release_date: str = "",
    source_name: str = "sample",
) -> ScheduleItem:
    return ScheduleItem(
        title=title,
        kind=kind,
        start_date=start_date,
        end_date=end_date,
        release_date=release_date,
        reservation_start="",
        seller_or_venue="",
        source_url=url,
        source_name=source_name,
        confidence=0.8,
        status="needs_review",
        review_reason="sample",
        notes="",
    )


def test_puroland_30th_goods_are_merged_as_one_schedule_item():
    cushion = schedule_item(
        "POMPOMPURIN 30th Anniversary クッション",
        url="https://www.puroland.jp/goods-feature/pompompurin30th/",
        start_date="2026-06-05",
    )
    pouch = schedule_item(
        "POMPOMPURIN 30th Anniversary ポーチ",
        url="https://www.puroland.jp/goods/pompompurin30th_008/",
    )

    merged = merge_related_items([cushion, pouch])

    assert len(merged) == 1
    assert merged[0].title == "POMPOMPURIN 30th Anniversary Goods"
    assert merged[0].kind == "product"
    assert merged[0].release_date == "2026-04-10"
    assert "2件の関連候補を1つの予定に集約しました" in merged[0].notes


def test_same_article_product_details_are_merged_into_campaign_level_item():
    campaign = schedule_item(
        "不二家洋菓子店 ペコちゃん×ポムポムプリンコラボレーション",
        kind="campaign",
        url="https://prtimes.jp/main/html/rd/p/000000428.000097396.html",
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    macaron = schedule_item(
        "ポムポムプリン30thペコちゃんとお祝いマカロン",
        url="https://prtimes.jp/main/html/rd/p/000000428.000097396.html",
        release_date="2026-06-01",
    )

    merged = merge_related_items([campaign, macaron])

    assert len(merged) == 1
    assert merged[0].title == "不二家洋菓子店 ペコちゃん×ポムポムプリンコラボレーション"
    assert merged[0].kind == "campaign"
    assert merged[0].start_date == "2026-06-01"
    assert merged[0].end_date == "2026-06-30"


def test_fragment_urls_share_the_same_display_group():
    base = schedule_item(
        "POMPOMPURIN 30th Anniversary Birthday Campaign",
        kind="event",
        url="https://www.puroland.jp/event-campaign/pompompurin30th/#h010501",
    )
    anchored = schedule_item(
        "POMPOMPURIN 30th Anniversary",
        kind="event",
        url="https://www.puroland.jp/event-campaign/pompompurin30th/#260303_food",
    )

    assert display_group_key(base) == display_group_key(anchored)


def test_character_profile_page_is_treated_as_noise():
    item = schedule_item(
        "ポムポムプリン｜サンリオ",
        kind="campaign",
        url="https://www.sanrio.co.jp/characters/pompompurin/?id=profile",
        start_date="2026-06-12",
        end_date="2026-12-12",
    )

    assert is_noise_item(item)
    assert merge_related_items([item]) == []
