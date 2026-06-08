from __future__ import annotations

import re
from urllib.parse import urlparse

from .storage import split_source_urls


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def is_broad_schedule_source_url(url: str) -> bool:
    parsed = urlparse(canonical_url(url))
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if host == "www.sanrio.co.jp":
        return path in {
            "",
            "/",
            "/news",
            "/news/goods",
            "/news/spots",
            "/news/campaign",
            "/news/shop",
            "/characters/pompompurin",
        }
    if host == "www.puroland.jp":
        return path in {"", "/"}
    return False


def is_public_detail_url(url: str) -> bool:
    parsed = urlparse(canonical_url(url))
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if not parsed.scheme or parsed.scheme not in {"http", "https"}:
        return False
    if is_broad_schedule_source_url(url):
        return False
    if host == "www.sanrio.co.jp":
        return bool(re.match(r"/news/(goods|spots|campaign|shop)/[^/]+$", path))
    if host == "www.puroland.jp":
        return bool(re.match(r"/(event-campaign|parade-show|goods-feature|food-feature|goods|food)/[^/]+$", path))
    if host == "prtimes.jp":
        return path.startswith("/main/html/rd/p/")
    if host == "www.atpress.ne.jp":
        return bool(re.match(r"/news/\d+$", path))
    return not is_broad_schedule_source_url(url)


def public_source_urls(source_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for url in split_source_urls(source_url):
        canonical = canonical_url(url)
        if not canonical or canonical in seen or not is_public_detail_url(canonical):
            continue
        seen.add(canonical)
        urls.append(url)
    return urls


def choose_public_source_url(source_url: str) -> str:
    urls = public_source_urls(source_url)
    return urls[0] if urls else ""
