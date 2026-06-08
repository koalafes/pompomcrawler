from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .aggregation import display_group_key, merge_related_items
from .aws_keys import block_keys_for_item, schedule_item_id
from .models import RawDocument, SCHEDULE_COLUMNS, ScheduleItem
from .storage import split_source_urls
from .url_policy import choose_public_source_url


METADATA_COLUMNS = {
    "item_id",
    "created_at",
    "updated_at",
    "deleted_at",
    "deleted_by",
    "delete_reason",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dynamo_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: dynamo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [dynamo_value(item) for item in value]
    return value


def plain_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_value(item) for item in value]
    return value


def schedule_record(item: ScheduleItem, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    timestamp = now_iso()
    record = {column: dynamo_value(item.to_dict().get(column, "")) for column in SCHEDULE_COLUMNS}
    record["item_id"] = existing.get("item_id") if existing and existing.get("item_id") else schedule_item_id(item)
    record["created_at"] = existing.get("created_at") if existing else timestamp
    record["updated_at"] = timestamp
    if existing:
        for column in ["deleted_at", "deleted_by", "delete_reason"]:
            if existing.get(column):
                record[column] = existing[column]
    return record


def item_from_record(record: dict[str, Any]) -> ScheduleItem:
    data = {column: plain_value(record.get(column, "")) for column in SCHEDULE_COLUMNS}
    return ScheduleItem.from_dict(data)


def public_payload(record: dict[str, Any]) -> dict[str, Any]:
    item = item_from_record(record)
    payload = item.to_dict()
    payload["public_source_url"] = choose_public_source_url(item.source_url)
    payload["item_id"] = record.get("item_id", schedule_item_id(item))
    payload["created_at"] = record.get("created_at", "")
    payload["updated_at"] = record.get("updated_at", "")
    return plain_value(payload)


def public_payloads(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [item_from_record(record) for record in records]
    merged_items = merge_related_items(items)
    payloads: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for item in merged_items:
        representative = representative_record(item, records)
        payload = item.to_dict()
        payload["public_source_url"] = choose_public_source_url(item.source_url)
        candidate_id = representative.get("item_id", schedule_item_id(item)) if representative else schedule_item_id(item)
        if candidate_id in used_ids:
            candidate_id = schedule_item_id(item)
        payload["item_id"] = unique_item_id(str(candidate_id), used_ids)
        payload["created_at"] = representative.get("created_at", "") if representative else ""
        payload["updated_at"] = max(
            [str(record.get("updated_at", "")) for record in related_records(item, records)] or [payload["created_at"]]
        )
        payloads.append(plain_value(payload))
    return payloads


def unique_item_id(candidate_id: str, used_ids: set[str]) -> str:
    item_id = candidate_id
    suffix = 2
    while item_id in used_ids:
        item_id = f"{candidate_id}-{suffix}"
        suffix += 1
    used_ids.add(item_id)
    return item_id


def representative_record(item: ScheduleItem, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    related = related_records(item, records)
    if not related:
        return None
    return max(
        related,
        key=lambda record: (
            record.get("status") == "confirmed",
            float(plain_value(record.get("confidence", 0)) or 0),
            str(record.get("updated_at", "")),
        ),
    )


def related_records(item: ScheduleItem, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_urls = split_source_urls(item.source_url)
    if not item_urls:
        return []
    related = []
    for record in records:
        record_urls = split_source_urls(str(record.get("source_url", "")))
        if item_urls.intersection(record_urls):
            related.append(record)
    return related


class DynamoScheduleStore:
    def __init__(self, schedule_table: Any, deleted_keys_table: Any, raw_table: Any | None = None) -> None:
        self.schedule_table = schedule_table
        self.deleted_keys_table = deleted_keys_table
        self.raw_table = raw_table

    @classmethod
    def from_env(cls) -> "DynamoScheduleStore":
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for AWS DynamoDB operations") from exc

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-northeast-1"
        dynamodb = boto3.resource("dynamodb", region_name=region)
        return cls(
            dynamodb.Table(required_env("SCHEDULE_ITEMS_TABLE")),
            dynamodb.Table(required_env("DELETED_KEYS_TABLE")),
            dynamodb.Table(os.getenv("RAW_DOCUMENTS_TABLE")) if os.getenv("RAW_DOCUMENTS_TABLE") else None,
        )

    def put_schedule_items(self, items: list[ScheduleItem]) -> int:
        changed = 0
        items = merge_related_items(items)
        existing_records = self.scan_schedule_records()
        records_by_id = {str(record.get("item_id", "")): record for record in existing_records if record.get("item_id")}
        records_by_group = {
            display_group_key(item_from_record(record)): record
            for record in existing_records
            if record.get("item_id") and record.get("status") != "excluded" and display_group_key(item_from_record(record))
        }
        failed_records_by_url: dict[str, list[dict[str, Any]]] = {}
        for record in existing_records:
            if "OpenAI extraction failed" not in str(record.get("review_reason", "")):
                continue
            if record.get("status") == "excluded":
                continue
            for url in split_source_urls(str(record.get("source_url", ""))):
                failed_records_by_url.setdefault(url, []).append(record)

        for item in items:
            if self.is_blocked(item):
                continue
            item_id = schedule_item_id(item)
            existing = records_by_id.get(item_id) or records_by_group.get(display_group_key(item)) or self.get_schedule_record(item_id)
            if existing and existing.get("status") == "excluded":
                continue
            if existing:
                item = merge_related_items([item_from_record(existing), item])[0]
            if "OpenAI extraction failed" not in item.review_reason:
                self.delete_failed_records_for_sources(item, item_id, failed_records_by_url)
            record = schedule_record(item, existing=existing)
            self.schedule_table.put_item(Item=record)
            records_by_id[item_id] = record
            if display_group_key(item):
                records_by_group[display_group_key(item)] = record
            changed += 1
        return changed

    def delete_failed_records_for_sources(
        self,
        item: ScheduleItem,
        item_id: str,
        failed_records_by_url: dict[str, list[dict[str, Any]]],
    ) -> None:
        seen_ids: set[str] = set()
        for url in split_source_urls(item.source_url):
            for record in failed_records_by_url.get(url, []):
                failed_id = str(record.get("item_id", ""))
                if not failed_id or failed_id == item_id or failed_id in seen_ids:
                    continue
                self.schedule_table.delete_item(Key={"item_id": failed_id})
                seen_ids.add(failed_id)

    def put_raw_documents(self, docs: list[RawDocument]) -> int:
        if self.raw_table is None:
            return 0
        for doc in docs:
            self.raw_table.put_item(Item=dynamo_value(doc.to_dict()))
        return len(docs)

    def public_items(self) -> list[dict[str, Any]]:
        records = [record for record in self.scan_schedule_records() if record.get("status") != "excluded"]
        return public_payloads(records)

    def admin_items(self) -> list[dict[str, Any]]:
        return [plain_value(record) for record in self.scan_schedule_records()]

    def successful_source_urls(self) -> set[str]:
        urls: set[str] = set()
        for record in self.scan_schedule_records():
            if record.get("status") == "excluded":
                continue
            if "OpenAI extraction failed" in str(record.get("review_reason", "")):
                continue
            urls.update(split_source_urls(str(record.get("source_url", ""))))
        return urls

    def failed_source_urls(self) -> set[str]:
        urls: set[str] = set()
        for record in self.scan_schedule_records():
            if record.get("status") == "excluded":
                continue
            if "OpenAI extraction failed" not in str(record.get("review_reason", "")):
                continue
            urls.update(split_source_urls(str(record.get("source_url", ""))))
        return urls

    def delete_item(self, item_id: str, *, deleted_by: str = "", reason: str = "") -> dict[str, Any]:
        record = self.get_schedule_record(item_id)
        if not record:
            raise KeyError(item_id)
        item = item_from_record(record)
        timestamp = now_iso()
        record["status"] = "excluded"
        record["deleted_at"] = timestamp
        record["deleted_by"] = deleted_by
        record["delete_reason"] = reason
        record["updated_at"] = timestamp
        self.schedule_table.put_item(Item=dynamo_value(record))
        for key in block_keys_for_item(item):
            self.deleted_keys_table.put_item(
                Item={
                    "block_key": key,
                    "item_id": item_id,
                    "created_at": timestamp,
                    "reason": reason,
                    "deleted_by": deleted_by,
                }
            )
        return public_payload(record)

    def restore_item(self, item_id: str) -> dict[str, Any]:
        record = self.get_schedule_record(item_id)
        if not record:
            raise KeyError(item_id)
        item = item_from_record(record)
        for key in block_keys_for_item(item):
            self.deleted_keys_table.delete_item(Key={"block_key": key})
        record["status"] = "needs_review"
        record["deleted_at"] = ""
        record["deleted_by"] = ""
        record["delete_reason"] = ""
        record["updated_at"] = now_iso()
        self.schedule_table.put_item(Item=dynamo_value(record))
        return public_payload(record)

    def is_blocked(self, item: ScheduleItem) -> bool:
        return any(self.get_block_record(key) for key in block_keys_for_item(item))

    def get_schedule_record(self, item_id: str) -> dict[str, Any] | None:
        response = self.schedule_table.get_item(Key={"item_id": item_id})
        return response.get("Item")

    def get_block_record(self, block_key: str) -> dict[str, Any] | None:
        response = self.deleted_keys_table.get_item(Key={"block_key": block_key})
        return response.get("Item")

    def scan_schedule_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        params: dict[str, Any] = {}
        while True:
            response = self.schedule_table.scan(**params)
            records.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                return records
            params["ExclusiveStartKey"] = last_key


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
