from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .aggregation import canonical_url
from .models import RawDocument, now_iso


USER_AGENT = "pompomcrawler/0.1 (+local research tool)"
TEXT_LIMIT = 20000


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._current_href = ""
        self._current_text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.image_candidates: list[tuple[str, str, int]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            attr_map = {key: value or "" for key, value in attrs}
            self._current_href = attr_map.get("href", "")
            self._current_text = []
        if tag == "meta":
            attr_map = {key.lower(): value or "" for key, value in attrs}
            name = (attr_map.get("property") or attr_map.get("name") or "").lower()
            content = attr_map.get("content", "")
            if name in {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"}:
                self.image_candidates.append((content, name, 0))
        if tag == "link":
            attr_map = {key.lower(): value or "" for key, value in attrs}
            rel = attr_map.get("rel", "").lower()
            if "image_src" in rel and attr_map.get("href"):
                self.image_candidates.append((attr_map["href"], rel, 1))
        if tag == "img":
            attr_map = {key.lower(): value or "" for key, value in attrs}
            src = first_present(attr_map, ["src", "data-src", "data-original", "data-lazy-src", "data-srcset"])
            src = first_srcset_url(src)
            if src:
                label = " ".join([attr_map.get("alt", ""), attr_map.get("class", ""), attr_map.get("id", "")])
                self.image_candidates.append((src, label, 2))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_href:
            link_text = normalize_space(" ".join(self._current_text))
            self.links.append((self._current_href, link_text))
            self._current_href = ""
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = normalize_space(data)
        if not text:
            return
        if self._in_title:
            self.title += text
        if self._current_href:
            self._current_text.append(text)
        self.text_parts.append(text)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def first_present(values: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = values.get(key, "").strip()
        if value:
            return value
    return ""


def first_srcset_url(value: str) -> str:
    if not value:
        return ""
    return value.split(",", maxsplit=1)[0].strip().split(" ", maxsplit=1)[0]


def select_image_url(base_url: str, candidates: list[tuple[str, str, int]]) -> str:
    ranked = []
    for raw_url, label, priority in candidates:
        image_url = normalize_space(raw_url)
        if not image_url or image_url.startswith(("data:", "blob:", "javascript:")):
            continue
        absolute = urljoin(base_url, image_url)
        lowered = f"{absolute} {label}".lower()
        if any(token in lowered for token in ["favicon", "apple-touch-icon", "logo", "sns-", "share", "blank", "spacer"]):
            continue
        if absolute.lower().split("?", maxsplit=1)[0].endswith(".svg"):
            continue
        relevance = 0
        if any(token in lowered for token in ["ポム", "pompom", "purin", "pn-", "goods", "event", "campaign", "cafe"]):
            relevance = -1
        ranked.append((priority, relevance, absolute))
    if not ranked:
        return ""
    ranked.sort()
    return ranked[0][2]


def fetch_url(url: str, timeout: int = 20) -> tuple[str, str, list[tuple[str, str]], str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    body = raw.decode(charset, errors="replace")
    parser = LinkExtractor()
    parser.feed(body)
    text = normalize_space(" ".join(parser.text_parts))[:TEXT_LIMIT]
    title = normalize_space(parser.title) or url
    image_url = select_image_url(url, parser.image_candidates)
    return title, text, parser.links, image_url


def keyword_match(value: str, keywords: Iterable[str]) -> bool:
    lowered = value.lower()
    return any(keyword.lower() in lowered for keyword in keywords if keyword)


def should_skip_discovered_link(source_url: str, target_url: str) -> bool:
    source = urlparse(canonical_url(source_url))
    target = urlparse(canonical_url(target_url))
    if canonical_url(source_url) == canonical_url(target_url):
        return True
    if source.netloc != target.netloc:
        return False
    source_path = source.path.rstrip("/")
    target_path = target.path.rstrip("/")
    if target_path.startswith(("/goods/pompompurin30th_", "/food/food_pompompurin30th_")):
        return True
    feature_match = re.match(r"^/(?P<section>goods|food)-feature/(?P<slug>[^/]+)$", source_path)
    if not feature_match:
        return False
    section = feature_match.group("section")
    slug = feature_match.group("slug")
    return target_path.startswith(f"/{section}/{slug}_")


def fetch_page_source(
    source: dict,
    keywords: list[str],
    max_discovered_links: int,
    delay_seconds: float = 0.2,
) -> list[RawDocument]:
    source_name = str(source.get("name", ""))
    url = str(source.get("url", ""))
    docs: list[RawDocument] = []
    try:
        title, text, links, image_url = fetch_url(url)
        docs.append(
            RawDocument(
                url=url,
                source_name=source_name,
                title=title,
                text=text,
                fetched_at=now_iso(),
                image_url=image_url,
            )
        )
    except Exception as exc:
        docs.append(
            RawDocument(
                url=url,
                source_name=source_name,
                title=f"FETCH_ERROR: {source_name}",
                text="",
                fetched_at=now_iso(),
                notes=str(exc),
            )
        )
        return docs

    discovered = 0
    seen = {canonical_url(url)}
    for href, label in links:
        absolute = canonical_url(urljoin(url, href))
        haystack = f"{absolute} {label}"
        if absolute in seen or should_skip_discovered_link(url, absolute) or not keyword_match(haystack, keywords):
            continue
        seen.add(absolute)
        try:
            time.sleep(delay_seconds)
            title, text, _, image_url = fetch_url(absolute)
            docs.append(
                RawDocument(
                    url=absolute,
                    source_name=f"{source_name} discovered",
                    title=title,
                    text=text,
                    fetched_at=now_iso(),
                    notes=f"Discovered from {url}",
                    image_url=image_url,
                )
            )
        except Exception as exc:
            docs.append(
                RawDocument(
                    url=absolute,
                    source_name=f"{source_name} discovered",
                    title=f"FETCH_ERROR: {label or absolute}",
                    text="",
                    fetched_at=now_iso(),
                    notes=str(exc),
                )
            )
        discovered += 1
        if discovered >= max_discovered_links:
            break
    return docs


def fetch_rss_source(source: dict, keywords: list[str]) -> list[RawDocument]:
    source_name = str(source.get("name", ""))
    url = str(source.get("url", ""))
    try:
        import feedparser

        feed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
        if getattr(feed, "bozo", False) and not feed.entries:
            raise RuntimeError(str(getattr(feed, "bozo_exception", "Failed to parse feed")))
    except Exception as exc:
        return [
            RawDocument(
                url=url,
                source_name=source_name,
                title=f"RSS_ERROR: {source_name}",
                text="",
                fetched_at=now_iso(),
                notes=str(exc),
            )
        ]

    docs: list[RawDocument] = []
    for entry in feed.entries:
        item_title = normalize_space(entry.get("title", ""))
        item_link = normalize_space(entry.get("link", url))
        description = normalize_space(entry.get("summary", "") or entry.get("description", ""))
        if not keyword_match(f"{item_title} {description} {item_link}", keywords):
            continue
        image_url = rss_image_url(entry, item_link)
        docs.append(
            RawDocument(
                url=item_link,
                source_name=source_name,
                title=item_title or item_link,
                text=f"{item_title}\n{description}",
                fetched_at=now_iso(),
                notes=f"RSS item from {url}",
                image_url=image_url,
            )
        )
    return docs


def rss_image_url(entry: object, base_url: str) -> str:
    candidates: list[tuple[str, str, int]] = []
    for field in ["media_thumbnail", "media_content", "links"]:
        values = entry.get(field, []) if hasattr(entry, "get") else getattr(entry, field, [])
        for item in values or []:
            if not isinstance(item, dict):
                continue
            image_url = item.get("url") or item.get("href") or ""
            mime_type = str(item.get("type") or "")
            rel = str(item.get("rel") or "")
            if image_url and ("image" in mime_type or rel == "enclosure" or field != "links"):
                candidates.append((str(image_url), field, 0))
    return select_image_url(base_url, candidates)
