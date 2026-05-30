from __future__ import annotations

import json

from pompomcrawler import aws_handlers
from pompomcrawler.aws_keys import block_keys_for_item, schedule_item_id
from pompomcrawler.dynamodb_store import DynamoScheduleStore
from pompomcrawler.models import ScheduleItem


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
