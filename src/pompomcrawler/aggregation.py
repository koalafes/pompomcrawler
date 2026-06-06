from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .models import ScheduleItem
from .storage import split_source_urls


@dataclass(frozen=True)
class CollectionSummary:
    title: str
    kind: str
    start_date: str = ""
    end_date: str = ""
    release_date: str = ""
    reservation_start: str = ""
    seller_or_venue: str = ""


PUROLAND_30TH_MAIN = "puroland:pompompurin30th:main"
PUROLAND_30TH_GOODS = "puroland:pompompurin30th:goods"
PUROLAND_30TH_MENU = "puroland:pompompurin30th:menu"
PUROLAND_30TH_SNS = "puroland:pompompurin30th:sns"
PUROLAND_30TH_GREETING = "puroland:pompompurin30th:greeting"
PUROLAND_30TH_ILLUMINATION = "puroland:pompompurin30th:illumination"
PUROLAND_30TH_ITSUDEMO = "puroland:pompompurin30th:itsudemopurin"

COLLECTION_SUMMARIES = {
    PUROLAND_30TH_MAIN: CollectionSummary(
        title="POMPOMPURIN 30th Anniversary",
        kind="event",
        start_date="2026-04-10",
        end_date="2026-12-31",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_GOODS: CollectionSummary(
        title="POMPOMPURIN 30th Anniversary Goods",
        kind="product",
        release_date="2026-04-10",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_MENU: CollectionSummary(
        title="POMPOMPURIN 30th Anniversary Menu",
        kind="product",
        release_date="2026-04-10",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_SNS: CollectionSummary(
        title="#ポムっと一息SNSキャンペーン",
        kind="campaign",
        start_date="2026-04-10",
        end_date="2026-11-30",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_GREETING: CollectionSummary(
        title="POMPOMPURIN 30th Anniversary Special Greeting",
        kind="event",
        start_date="2026-06-06",
        end_date="2026-08-31",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_ILLUMINATION: CollectionSummary(
        title="POMPOMPURIN 30th Anniversary Illumination",
        kind="event",
        seller_or_venue="サンリオピューロランド",
    ),
    PUROLAND_30TH_ITSUDEMO: CollectionSummary(
        title="3Dデジタルフィギュア「いつでもプリン」",
        kind="product",
        release_date="2026-06-08",
        seller_or_venue="サンリオピューロランド",
    ),
}


def normalize_for_group(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower())


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def canonical_source_urls(source_url: str) -> set[str]:
    return {canonical_url(url) for url in split_source_urls(source_url) if canonical_url(url)}


def primary_date(item: ScheduleItem) -> str:
    return item.release_date or item.start_date or item.reservation_start or item.end_date


def collection_key(item: ScheduleItem) -> str:
    urls = canonical_source_urls(item.source_url)
    title_blob = f"{item.title} {item.notes} {item.review_reason}".lower()
    has_puroland_source = any(urlparse(url).netloc == "www.puroland.jp" for url in urls)

    if any("/goods-feature/pompompurin30th" in url or "/goods/pompompurin30th_" in url for url in urls):
        return PUROLAND_30TH_GOODS
    if any("/food-feature/food_pompompurin30th" in url or "/food/food_pompompurin30th_" in url for url in urls):
        return PUROLAND_30TH_MENU
    if any("/event-campaign/pompompurin30th_sns_campaign" in url for url in urls):
        return PUROLAND_30TH_SNS
    if any("/parade-show/pompompurin30th_illumination" in url for url in urls):
        return PUROLAND_30TH_ILLUMINATION
    if any("/event-campaign/pompompurin30th_itsudemopurin" in url for url in urls):
        return PUROLAND_30TH_ITSUDEMO
    if any("/event-campaign/pompompurin30th" in url for url in urls):
        if any(token in title_blob for token in ["goods", "merchandise", "グッズ", "商品", "menu", "メニュー", "food"]):
            return PUROLAND_30TH_MENU if any(token in title_blob for token in ["menu", "メニュー", "food"]) else PUROLAND_30TH_GOODS
        if any(token in title_blob for token in ["greeting", "グリーティング"]):
            return PUROLAND_30TH_GREETING
        if any(token in title_blob for token in ["sns", "ポムっと一息"]):
            return PUROLAND_30TH_SNS
        return PUROLAND_30TH_MAIN
    if has_puroland_source and any(token in title_blob for token in ["pompompurin 30th anniversary", "ポムポムプリン30周年"]):
        if any(token in title_blob for token in ["sns", "ポムっと一息"]):
            return PUROLAND_30TH_SNS
        if any(token in title_blob for token in ["goods", "merchandise", "グッズ", "商品"]):
            return PUROLAND_30TH_GOODS
        if any(token in title_blob for token in ["menu", "メニュー", "food"]):
            return PUROLAND_30TH_MENU
        return PUROLAND_30TH_MAIN
    if has_puroland_source and any(token in title_blob for token in ["sns", "ポムっと一息"]):
        return PUROLAND_30TH_SNS
    return ""


def article_group_key(item: ScheduleItem) -> str:
    urls = sorted(canonical_source_urls(item.source_url))
    for url in urls:
        if is_article_or_feature_url(url):
            return f"article:{url}"
    return ""


def is_article_or_feature_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    host = parsed.netloc.lower()
    if host == "prtimes.jp" and path.startswith("/main/html/rd/p/"):
        return True
    if host == "www.atpress.ne.jp" and re.match(r"/news/\d+$", path):
        return True
    if host == "www.sanrio.co.jp" and re.match(r"/news/(goods|spots|campaign|shop)/[^/]+$", path):
        return True
    if host == "www.puroland.jp" and re.match(r"/(event-campaign|parade-show|goods-feature|food-feature)/[^/]+$", path):
        return True
    return False


def display_group_key(item: ScheduleItem) -> str:
    key = collection_key(item)
    if key:
        return f"collection:{key}"
    key = article_group_key(item)
    if key:
        return key
    urls = sorted(canonical_source_urls(item.source_url))
    if not urls:
        return ""
    return "|".join(
        [
            "url-title-date",
            urls[0],
            normalize_for_group(item.title),
            item.kind or "",
            primary_date(item),
        ]
    )


def merge_related_items(items: list[ScheduleItem]) -> list[ScheduleItem]:
    groups: dict[str, list[ScheduleItem]] = {}
    passthrough: list[ScheduleItem] = []
    for item in items:
        if is_noise_item(item):
            continue
        key = display_group_key(item)
        if not key:
            passthrough.append(item)
            continue
        groups.setdefault(key, []).append(item)

    merged = [merge_item_group(group) for group in groups.values()]
    return [*passthrough, *merged]


def is_noise_item(item: ScheduleItem) -> bool:
    urls = canonical_source_urls(item.source_url)
    title = normalize_for_group(item.title)
    if any(urlparse(url).netloc == "www.sanrio.co.jp" and urlparse(url).path.rstrip("/") == "/characters/pompompurin" for url in urls):
        if title in {normalize_for_group("ポムポムプリン｜サンリオ"), normalize_for_group("ポムポムプリン サンリオ")}:
            return True
    return False


def merge_item_group(items: list[ScheduleItem]) -> ScheduleItem:
    if len(items) == 1:
        return items[0]

    key = collection_key(items[0])
    summary = COLLECTION_SUMMARIES.get(key)
    base = choose_representative(items)
    merged = ScheduleItem.from_dict(base.to_dict())
    merged.confidence = max(item.confidence for item in items)
    merged.source_url = " | ".join(sorted({url for item in items for url in split_source_urls(item.source_url)}))
    merged.source_name = " | ".join(sorted({name for item in items for name in split_source_names(item.source_name)}))
    merged.image_url = next((item.image_url for item in items if item.image_url), merged.image_url)
    merged.review_reason = merge_texts(item.review_reason for item in items)
    merged.notes = collection_notes(items, summary)
    merged.status = merged_status(items)

    if summary:
        merged.title = summary.title
        merged.kind = summary.kind
        merged.start_date = summary.start_date
        merged.end_date = summary.end_date
        merged.release_date = summary.release_date
        merged.reservation_start = summary.reservation_start
        merged.seller_or_venue = summary.seller_or_venue
    else:
        fill_missing_fields(merged, items)
    return merged


def choose_representative(items: list[ScheduleItem]) -> ScheduleItem:
    return max(
        items,
        key=lambda item: (
            item.status == "confirmed",
            item.kind in {"event", "campaign", "reservation"},
            item.kind not in {"", "other"},
            bool(item.start_date or item.release_date or item.reservation_start),
            not re.search(r"\s-\s|会場", item.title),
            item.confidence,
            -len(item.title),
        ),
    )


def split_source_names(value: str) -> set[str]:
    return {name.strip() for name in value.split(" | ") if name.strip()}


def merge_texts(values) -> str:
    texts: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in texts:
            texts.append(text)
    return " / duplicate candidate: ".join(texts)


def collection_notes(items: list[ScheduleItem], summary: CollectionSummary | None) -> str:
    notes = [item.notes.strip() for item in items if item.notes.strip()]
    examples = []
    for item in items:
        title = item.title.strip()
        if summary and title == summary.title:
            continue
        if title and title not in examples:
            examples.append(title)
        if len(examples) >= 6:
            break
    prefix = f"{len(items)}件の関連候補を1つの予定に集約しました。"
    if examples:
        prefix = f"{prefix} 例: {', '.join(examples)}"
    return " / ".join([prefix, *unique_texts(notes)])


def unique_texts(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return unique


def merged_status(items: list[ScheduleItem]) -> str:
    statuses = [item.status for item in items]
    if "confirmed" in statuses:
        return "confirmed"
    if all(status == "excluded" for status in statuses):
        return "excluded"
    return "needs_review"


def earliest_date(values) -> str:
    dates = sorted({str(value) for value in values if str(value or "").strip()})
    return dates[0] if dates else ""


def fill_missing_fields(merged: ScheduleItem, items: list[ScheduleItem]) -> None:
    for field in ["start_date", "end_date", "release_date", "reservation_start", "seller_or_venue"]:
        if getattr(merged, field):
            continue
        value = next((getattr(item, field) for item in items if getattr(item, field)), "")
        setattr(merged, field, value)
