from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from .models import ScheduleItem
from .storage import split_source_urls


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_for_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower())


def item_signature(item: ScheduleItem) -> str:
    parts = [
        normalize_for_key(item.title),
        item.kind or "",
        item.start_date or "",
        item.end_date or "",
        item.release_date or "",
        item.reservation_start or "",
    ]
    return "|".join(parts)


def item_signature_key(item: ScheduleItem) -> str:
    return f"item:{digest(item_signature(item))}"


def source_url_keys(source_url: str) -> set[str]:
    return {f"url:{digest(url)}" for url in split_source_urls(source_url)}


def block_keys_for_item(item: ScheduleItem) -> set[str]:
    return {*source_url_keys(item.source_url), item_signature_key(item)}


def schedule_item_id(item: ScheduleItem) -> str:
    identity = "|".join(
        [
            sorted(split_source_urls(item.source_url))[0] if split_source_urls(item.source_url) else "",
            item_signature(item),
            item.source_name or "",
        ]
    )
    return digest(identity)[:32]


def any_blocked(keys: Iterable[str], blocked: Iterable[str]) -> bool:
    blocked_set = set(blocked)
    return any(key in blocked_set for key in keys)
