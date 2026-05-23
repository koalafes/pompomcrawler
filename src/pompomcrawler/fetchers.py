from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

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


def fetch_url(url: str, timeout: int = 20) -> tuple[str, str, list[tuple[str, str]]]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    body = raw.decode(charset, errors="replace")
    parser = LinkExtractor()
    parser.feed(body)
    text = normalize_space(" ".join(parser.text_parts))[:TEXT_LIMIT]
    title = normalize_space(parser.title) or url
    return title, text, parser.links


def keyword_match(value: str, keywords: Iterable[str]) -> bool:
    lowered = value.lower()
    return any(keyword.lower() in lowered for keyword in keywords if keyword)


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
        title, text, links = fetch_url(url)
        docs.append(RawDocument(url=url, source_name=source_name, title=title, text=text, fetched_at=now_iso()))
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
    seen = {url}
    for href, label in links:
        absolute = urljoin(url, href)
        haystack = f"{absolute} {label}"
        if absolute in seen or not keyword_match(haystack, keywords):
            continue
        seen.add(absolute)
        try:
            time.sleep(delay_seconds)
            title, text, _ = fetch_url(absolute)
            docs.append(
                RawDocument(
                    url=absolute,
                    source_name=f"{source_name} discovered",
                    title=title,
                    text=text,
                    fetched_at=now_iso(),
                    notes=f"Discovered from {url}",
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
        docs.append(
            RawDocument(
                url=item_link,
                source_name=source_name,
                title=item_title or item_link,
                text=f"{item_title}\n{description}",
                fetched_at=now_iso(),
                notes=f"RSS item from {url}",
            )
        )
    return docs
