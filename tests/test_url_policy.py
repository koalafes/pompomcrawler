from pompomcrawler.url_policy import (
    choose_public_source_url,
    is_broad_schedule_source_url,
    is_public_detail_url,
)


def test_character_profile_page_is_not_a_public_detail_url():
    url = "https://www.sanrio.co.jp/characters/pompompurin/?id=profile"

    assert is_broad_schedule_source_url(url)
    assert not is_public_detail_url(url)


def test_choose_public_source_url_prefers_schedule_detail_page():
    source_url = " | ".join(
        [
            "https://www.sanrio.co.jp/characters/pompompurin/?id=profile",
            "https://www.sanrio.co.jp/news/spots/pn-pop-up-store-loft-20260528/",
        ]
    )

    assert choose_public_source_url(source_url) == "https://www.sanrio.co.jp/news/spots/pn-pop-up-store-loft-20260528/"


def test_broad_listing_pages_are_not_public_detail_urls():
    for url in [
        "https://www.sanrio.co.jp/news/",
        "https://www.sanrio.co.jp/news/goods/",
        "https://www.puroland.jp/",
    ]:
        assert is_broad_schedule_source_url(url)
        assert not is_public_detail_url(url)
