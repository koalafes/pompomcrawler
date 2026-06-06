from __future__ import annotations

import json

from pompomcrawler import aws_handlers
from pompomcrawler.aws_keys import block_keys_for_item, schedule_item_id
from pompomcrawler.dynamodb_store import DynamoScheduleStore
from pompomcrawler.models import RawDocument, ScheduleItem


class MemoryTable:
    def __init__(self, key_name: str) -> None:
        self.key_name = key_name
        self.items: dict[str, dict] = {}

    def put_item(self, Item: dict) -> dict:
        self.items[Item[self.key_name]] = dict(Item)
        return {}

    def get_item(self, Key: dict) -> dict:
        item = self.items.get(Key[self.key_name])
        return {"Item": item} if item else {}

    def delete_item(self, Key: dict) -> dict:
        self.items.pop(Key[self.key_name], None)
        return {}

    def scan(self, **kwargs) -> dict:
        return {"Items": list(self.items.values())}


def schedule_item(title: str = "ポムポムプリン イベント", url: str = "https://example.com/event") -> ScheduleItem:
    return ScheduleItem(
        title=title,
        kind="event",
        start_date="2026-06-01",
        end_date="2026-06-30",
        release_date="",
        reservation_start="",
        seller_or_venue="東京",
        source_url=url,
        source_name="manual",
        confidence=0.9,
        status="needs_review",
        review_reason="sample",
        notes="",
    )


def memory_store() -> DynamoScheduleStore:
    return DynamoScheduleStore(MemoryTable("item_id"), MemoryTable("block_key"), MemoryTable("url"))


def raw_doc(url: str) -> RawDocument:
    return RawDocument(
        url=url,
        source_name="sample",
        title="ポムポムプリン",
        text="ポムポムプリン",
        fetched_at="2026-06-03T00:00:00+00:00",
    )


def test_delete_blocks_future_reinsertion_and_restore_allows_it():
    store = memory_store()
    item = schedule_item()
    item_id = schedule_item_id(item)

    assert store.put_schedule_items([item]) == 1
    deleted = store.delete_item(item_id, deleted_by="admin@example.com", reason="wrong item")

    assert deleted["status"] == "excluded"
    assert store.get_schedule_record(item_id)["deleted_by"] == "admin@example.com"
    assert set(store.deleted_keys_table.items) == block_keys_for_item(item)
    assert store.put_schedule_items([item]) == 0

    restored = store.restore_item(item_id)

    assert restored["status"] == "needs_review"
    assert store.deleted_keys_table.items == {}
    assert store.put_schedule_items([item]) == 1


def test_put_schedule_items_replaces_failed_record_for_same_source_url():
    store = memory_store()
    failed = schedule_item(title="FETCH_ERROR: ポムポムプリン", url="https://example.com/event")
    failed.start_date = ""
    failed.end_date = ""
    failed.confidence = 0.2
    failed.review_reason = "OpenAI extraction failed: openai package could not be imported"
    fresh = schedule_item(title="ポムポムプリン イベント", url="https://example.com/event")

    store.put_schedule_items([failed])
    failed_id = schedule_item_id(failed)
    store.put_schedule_items([fresh])
    fresh_id = schedule_item_id(fresh)

    assert failed_id not in store.schedule_table.items
    assert fresh_id in store.schedule_table.items


def test_public_items_aggregate_existing_collection_records():
    store = memory_store()
    first = schedule_item(
        title="POMPOMPURIN 30th Anniversary クッション",
        url="https://www.puroland.jp/goods-feature/pompompurin30th/",
    )
    second = schedule_item(
        title="POMPOMPURIN 30th Anniversary ポーチ",
        url="https://www.puroland.jp/goods/pompompurin30th_008/",
    )

    store.put_schedule_items([first])
    store.put_schedule_items([second])
    public_items = store.public_items()

    assert len(public_items) == 1
    assert public_items[0]["title"] == "POMPOMPURIN 30th Anniversary Goods"
    assert public_items[0]["item_id"]


def test_public_items_keep_unique_ids_for_overlapping_collection_sources():
    store = memory_store()
    main = schedule_item(
        title="POMPOMPURIN 30th Anniversary",
        url="https://www.puroland.jp/event-campaign/pompompurin30th/",
    )
    goods = schedule_item(
        title="POMPOMPURIN 30th Anniversary Goods",
        url="https://www.puroland.jp/event-campaign/pompompurin30th/",
    )

    store.put_schedule_items([main, goods])
    item_ids = [item["item_id"] for item in store.public_items()]

    assert len(item_ids) == len(set(item_ids))


def test_select_documents_for_extraction_prioritizes_direct_detail_pages():
    docs = [
        raw_doc("https://www.sanrio.co.jp/news/"),
        raw_doc("https://example.com/discovered"),
        raw_doc("https://www.sanrio.co.jp/news/spots/pn-biwako-fireworks-20260601/"),
    ]

    selected = aws_handlers.select_documents_for_extraction(
        docs,
        direct_url_ranks={
            "https://www.sanrio.co.jp/news/": 0,
            "https://www.sanrio.co.jp/news/spots/pn-biwako-fireworks-20260601/": 1,
        },
        successful_urls=set(),
        failed_urls=set(),
        max_docs=2,
    )

    assert [doc.url for doc in selected] == [
        "https://www.sanrio.co.jp/news/spots/pn-biwako-fireworks-20260601/",
        "https://www.sanrio.co.jp/news/",
    ]


def test_select_documents_for_extraction_skips_successful_urls_unless_failed():
    docs = [
        raw_doc("https://example.com/success"),
        raw_doc("https://example.com/retry"),
        raw_doc("https://example.com/new"),
    ]

    selected = aws_handlers.select_documents_for_extraction(
        docs,
        direct_url_ranks={},
        successful_urls={"https://example.com/success", "https://example.com/retry"},
        failed_urls={"https://example.com/retry"},
        max_docs=10,
    )

    assert {doc.url for doc in selected} == {"https://example.com/retry", "https://example.com/new"}


def test_select_documents_for_extraction_skips_successful_anchor_variants():
    docs = [
        raw_doc("https://www.puroland.jp/event-campaign/pompompurin30th/#h010300"),
        raw_doc("https://www.puroland.jp/event-campaign/pompompurin30th/#h010600"),
        raw_doc("https://www.puroland.jp/event-campaign/pompompurin30th_sns_campaign/"),
    ]

    selected = aws_handlers.select_documents_for_extraction(
        docs,
        direct_url_ranks={},
        successful_urls={"https://www.puroland.jp/event-campaign/pompompurin30th/"},
        failed_urls=set(),
        max_docs=10,
    )

    assert [doc.url for doc in selected] == [
        "https://www.puroland.jp/event-campaign/pompompurin30th_sns_campaign/"
    ]


def test_public_api_hides_excluded_and_admin_delete_requires_group(monkeypatch):
    store = memory_store()
    item = schedule_item()
    item_id = schedule_item_id(item)
    store.put_schedule_items([item])
    monkeypatch.setattr(aws_handlers.DynamoScheduleStore, "from_env", classmethod(lambda cls: store))

    public_response = aws_handlers.api_handler(api_event("GET", "/items"), None)
    public_payload = json.loads(public_response["body"])

    assert public_response["statusCode"] == 200
    assert public_payload["items"][0]["item_id"] == item_id

    denied = aws_handlers.api_handler(api_event("DELETE", f"/admin/items/{item_id}"), None)
    assert denied["statusCode"] == 403

    deleted = aws_handlers.api_handler(
        api_event(
            "DELETE",
            f"/admin/items/{item_id}",
            body={"reason": "wrong item"},
            groups=["calendar-admin"],
        ),
        None,
    )
    assert deleted["statusCode"] == 200

    public_response = aws_handlers.api_handler(api_event("GET", "/items"), None)
    assert json.loads(public_response["body"])["items"] == []


def test_admin_email_can_delete_when_group_claim_missing(monkeypatch):
    store = memory_store()
    item = schedule_item()
    item_id = schedule_item_id(item)
    store.put_schedule_items([item])
    monkeypatch.setattr(aws_handlers.DynamoScheduleStore, "from_env", classmethod(lambda cls: store))
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")

    deleted = aws_handlers.api_handler(
        api_event("DELETE", f"/admin/items/{item_id}", body={"reason": "wrong item"}),
        None,
    )

    assert deleted["statusCode"] == 200
    assert store.get_schedule_record(item_id)["status"] == "excluded"


def api_event(method: str, path: str, *, body: dict | None = None, groups: list[str] | None = None) -> dict:
    claims = {"email": "admin@example.com"}
    if groups:
        claims["cognito:groups"] = groups
    return {
        "rawPath": path,
        "body": json.dumps(body or {}),
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": claims}},
        },
    }
