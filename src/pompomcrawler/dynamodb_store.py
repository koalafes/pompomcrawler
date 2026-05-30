from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .aws_keys import block_keys_for_item, schedule_item_id
from .models import RawDocument, SCHEDULE_COLUMNS, ScheduleItem


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
    record["item_id"] = schedule_item_id(item)
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
    payload["item_id"] = record.get("item_id", schedule_item_id(item))
    payload["created_at"] = record.get("created_at", "")
    payload["updated_at"] = record.get("updated_at", "")
    return plain_value(payload)


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
        for item in items:
            if self.is_blocked(item):
                continue
            item_id = schedule_item_id(item)
            existing = self.get_schedule_record(item_id)
            if existing and existing.get("status") == "excluded":
                continue
            record = schedule_record(item, existing=existing)
            self.schedule_table.put_item(Item=record)
            changed += 1
        return changed

    def put_raw_documents(self, docs: list[RawDocument]) -> int:
        if self.raw_table is None:
            return 0
        for doc in docs:
            self.raw_table.put_item(Item=dynamo_value(doc.to_dict()))
        return len(docs)

    def public_items(self) -> list[dict[str, Any]]:
        return [public_payload(record) for record in self.scan_schedule_records() if record.get("status") != "excluded"]

    def admin_items(self) -> list[dict[str, Any]]:
        return [plain_value(record) for record in self.scan_schedule_records()]

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
