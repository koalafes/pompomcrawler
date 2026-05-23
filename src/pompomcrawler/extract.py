from __future__ import annotations

import json
import os
import re
from datetime import date
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from .models import RawDocument, ScheduleItem


EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["product", "event", "campaign", "reservation", "other"],
                    },
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "release_date": {"type": "string"},
                    "reservation_start": {"type": "string"},
                    "seller_or_venue": {"type": "string"},
                    "confidence": {"type": "number"},
                    "status": {
                        "type": "string",
                        "enum": ["candidate", "needs_review", "confirmed", "excluded"],
                    },
                    "review_reason": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": [
                    "title",
                    "kind",
                    "start_date",
                    "end_date",
                    "release_date",
                    "reservation_start",
                    "seller_or_venue",
                    "confidence",
                    "status",
                    "review_reason",
                    "notes",
                ],
            },
        }
    },
    "required": ["items"],
}


SYSTEM_PROMPT = """You extract Japanese product and event schedule data about Pom Pom Purin.
Return JSON only according to the schema.
Prefer recall over precision: keep weak but plausible Pom Pom Purin goods, event, campaign, reservation, collaboration, cafe, store, or limited-time candidates.
Use ISO dates YYYY-MM-DD when dates are explicit. Leave unknown dates as empty strings.
Set status to needs_review unless the text is clearly unrelated, in which case use excluded.
Do not invent missing dates, venues, sellers, or product names."""


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        return
    try:
        load_dotenv()
    except AssertionError:
        return


def extract_items_from_documents(docs: Iterable[RawDocument], use_openai: bool = True) -> list[ScheduleItem]:
    load_dotenv_if_available()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    extractor = OpenAIExtractor(model=model) if api_key and use_openai else None

    items: list[ScheduleItem] = []
    for doc in docs:
        if not doc.text and not doc.title:
            items.append(fallback_item(doc, "No text was fetched; review the source URL manually."))
            continue
        try:
            doc_items = extractor.extract(doc) if extractor else heuristic_extract(doc)
        except Exception as exc:
            doc_items = [fallback_item(doc, f"OpenAI extraction failed: {exc}")]
        items.extend(doc_items)
    return items


@dataclass
class OpenAIExtractor:
    model: str

    def extract(self, doc: RawDocument) -> list[ScheduleItem]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        client = OpenAI(timeout=30.0, max_retries=1)
        user_content = (
            f"Source name: {doc.source_name}\n"
            f"URL: {doc.url}\n"
            f"Page title: {doc.title}\n"
            f"Notes: {doc.notes}\n"
            "Text:\n"
            f"{doc.text[:12000]}"
        )
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "pompompurin_extraction",
                    "strict": True,
                    "schema": EXTRACTION_SCHEMA,
                }
            },
        )
        payload = json.loads(response.output_text)
        return [
            ScheduleItem(
                source_url=doc.url,
                source_name=doc.source_name,
                **normalize_openai_item(item, doc),
            )
            for item in payload.get("items", [])
        ]


def normalize_openai_item(item: dict, doc: RawDocument) -> dict:
    title = str(item.get("title") or doc.title or doc.url)
    status = str(item.get("status") or "needs_review")
    if status == "candidate":
        status = "needs_review"
    return {
        "title": title,
        "kind": str(item.get("kind") or "other"),
        "start_date": str(item.get("start_date") or ""),
        "end_date": str(item.get("end_date") or ""),
        "release_date": str(item.get("release_date") or ""),
        "reservation_start": str(item.get("reservation_start") or ""),
        "seller_or_venue": str(item.get("seller_or_venue") or ""),
        "confidence": float(item.get("confidence") or 0.5),
        "status": status,
        "review_reason": str(item.get("review_reason") or "OpenAI extracted this candidate."),
        "notes": str(item.get("notes") or doc.notes),
    }


def heuristic_extract(doc: RawDocument) -> list[ScheduleItem]:
    haystack = f"{doc.title}\n{doc.text}"
    related = any(keyword in haystack.lower() for keyword in ["ポムポムプリン", "ぽむぽむぷりん", "pompompurin", "pom pom purin"])
    if not related:
        return [fallback_item(doc, "No Pom Pom Purin keyword was found in the fetched text.", status="excluded", confidence=0.1)]

    kind = "other"
    if re.search(r"発売|新商品|グッズ|販売|予約", haystack):
        kind = "product"
    if re.search(r"イベント|開催|フェア|カフェ|ポップアップ|POP.?UP", haystack, re.IGNORECASE):
        kind = "event"
    if re.search(r"キャンペーン|特典|ノベルティ", haystack):
        kind = "campaign"
    if re.search(r"予約開始|予約受付|予約販売", haystack):
        kind = "reservation"

    guessed_date = guess_first_japanese_date(doc.title) or guess_first_japanese_date(doc.text)
    start_date = guessed_date if kind in {"event", "campaign"} else ""
    release_date = guessed_date if kind == "product" else ""
    reservation_start = guessed_date if kind == "reservation" else ""

    return [
        ScheduleItem(
            title=doc.title or first_sentence(doc.text) or doc.url,
            kind=kind,
            start_date=start_date,
            end_date="",
            release_date=release_date,
            reservation_start=reservation_start,
            seller_or_venue="",
            source_url=doc.url,
            source_name=doc.source_name,
            confidence=0.45,
            status="needs_review",
            review_reason="OpenAI API was not available; heuristic keyword extraction created this candidate.",
            notes=doc.notes,
        )
    ]


def guess_first_japanese_date(text: str, default_year: int | None = None) -> str:
    default_year = default_year or date.today().year
    patterns = [
        re.compile(r"(?P<year>20\d{2})年\s*(?P<month>1[0-2]|0?[1-9])月\s*(?P<day>3[01]|[12]\d|0?[1-9])日"),
        re.compile(r"(?P<month>1[0-2]|0?[1-9])月\s*(?P<day>3[01]|[12]\d|0?[1-9])日"),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        year = int(match.groupdict().get("year") or default_year)
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return ""
    return ""


def fallback_item(doc: RawDocument, reason: str, status: str = "needs_review", confidence: float = 0.2) -> ScheduleItem:
    return ScheduleItem(
        title=doc.title or doc.url,
        kind="other",
        start_date="",
        end_date="",
        release_date="",
        reservation_start="",
        seller_or_venue="",
        source_url=doc.url,
        source_name=doc.source_name,
        confidence=confidence,
        status=status,
        review_reason=reason,
        notes=doc.notes,
    )


def first_sentence(text: str) -> str:
    return re.split(r"[。.!?]", text.strip(), maxsplit=1)[0][:120]


def normalize_for_match(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower())


def merge_duplicates(items: Iterable[ScheduleItem]) -> list[ScheduleItem]:
    merged: list[ScheduleItem] = []
    for item in items:
        match = find_duplicate(item, merged)
        if match is None:
            merged.append(item)
            continue
        match.confidence = max(match.confidence, item.confidence)
        if item.source_url and item.source_url not in match.source_url:
            match.source_url = f"{match.source_url} | {item.source_url}" if match.source_url else item.source_url
        if item.source_name and item.source_name not in match.source_name:
            match.source_name = f"{match.source_name} | {item.source_name}" if match.source_name else item.source_name
        if item.review_reason and item.review_reason not in match.review_reason:
            match.review_reason = f"{match.review_reason} / duplicate candidate: {item.review_reason}"
        for field in ["start_date", "end_date", "release_date", "reservation_start", "seller_or_venue"]:
            if not getattr(match, field) and getattr(item, field):
                setattr(match, field, getattr(item, field))
        if match.kind in {"", "other"} and item.kind not in {"", "other"}:
            match.kind = item.kind
    return merged


def find_duplicate(item: ScheduleItem, candidates: list[ScheduleItem]) -> ScheduleItem | None:
    item_title = normalize_for_match(item.title)
    item_date = item.release_date or item.start_date or item.reservation_start
    for candidate in candidates:
        candidate_date = candidate.release_date or candidate.start_date or candidate.reservation_start
        if item.source_url and candidate.source_url and item.source_url in candidate.source_url:
            return candidate
        title_ratio = SequenceMatcher(None, item_title, normalize_for_match(candidate.title)).ratio()
        compatible_date = not item_date or not candidate_date or item_date == candidate_date
        if title_ratio >= 0.86 and compatible_date:
            return candidate
    return None
