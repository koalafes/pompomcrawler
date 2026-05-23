from pompomcrawler.fetchers import LinkExtractor, select_image_url


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
