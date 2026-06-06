from pompomcrawler.fetchers import LinkExtractor, select_image_url, should_skip_discovered_link


def test_link_extractor_prefers_og_image():
    parser = LinkExtractor()
    parser.feed(
        """
        <html>
          <head>
            <meta property="og:image" content="/images/pompompurin-event.jpg">
          </head>
          <body>
            <img src="/images/logo.svg" alt="logo">
            <a href="/news">ポムポムプリン ニュース</a>
          </body>
        </html>
        """
    )

    image_url = select_image_url("https://example.com/pages/detail", parser.image_candidates)

    assert image_url == "https://example.com/images/pompompurin-event.jpg"


def test_select_image_url_skips_tracking_images():
    image_url = select_image_url(
        "https://example.com/news/",
        [
            ("/favicon.ico", "favicon", 0),
            ("/assets/spacer.gif", "spacer", 1),
            ("/assets/pompompurin-main.jpg", "ポムポムプリン", 2),
        ],
    )

    assert image_url == "https://example.com/assets/pompompurin-main.jpg"


def test_discovered_same_page_anchor_is_skipped():
    assert should_skip_discovered_link(
        "https://www.puroland.jp/event-campaign/pompompurin30th/",
        "https://www.puroland.jp/event-campaign/pompompurin30th/#h010300",
    )


def test_discovered_anniversary_sku_pages_are_skipped():
    assert should_skip_discovered_link(
        "https://www.puroland.jp/goods-feature/pompompurin30th/",
        "https://www.puroland.jp/goods/pompompurin30th_011_a/",
    )
    assert should_skip_discovered_link(
        "https://www.puroland.jp/food-feature/food_pompompurin30th/",
        "https://www.puroland.jp/food/food_pompompurin30th_004/",
    )
