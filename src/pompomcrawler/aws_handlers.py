from __future__ import annotations

import json
import os
from typing import Any

from .config import DEFAULT_CONFIG, load_config
from .dynamodb_store import DynamoScheduleStore
from .extract import extract_items_from_documents
from .fetchers import fetch_page_source, fetch_rss_source


CORS_HEADERS = {
    "access-control-allow-origin": os.getenv("CORS_ALLOW_ORIGIN", "*"),
    "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
}


def api_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(204, {})

    store = DynamoScheduleStore.from_env()
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath") or event.get("path") or "/"

    try:
        if method == "GET" and path == "/items":
            return response(200, {"items": store.public_items()})
        if method == "GET" and path == "/admin/items":
            require_admin(event)
            return response(200, {"items": store.admin_items()})
        if method == "DELETE" and path.startswith("/admin/items/"):
            claims = require_admin(event)
            item_id = path.removeprefix("/admin/items/").strip("/")
            body = json.loads(event.get("body") or "{}")
            item = store.delete_item(item_id, deleted_by=admin_name(claims), reason=str(body.get("reason", "")))
            return response(200, {"item": item})
        if method == "POST" and path.startswith("/admin/items/") and path.endswith("/restore"):
            require_admin(event)
            item_id = path.removeprefix("/admin/items/").removesuffix("/restore").strip("/")
            item = store.restore_item(item_id)
            return response(200, {"item": item})
    except PermissionError:
        return response(403, {"error": "calendar-admin group is required"})
    except KeyError:
        return response(404, {"error": "item not found"})
    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON body"})

    return response(404, {"error": "not found"})


def crawler_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    load_openai_secret_if_configured()
    store = DynamoScheduleStore.from_env()
    config = load_config(os.getenv("POMPOM_CONFIG_PATH", str(DEFAULT_CONFIG)))
    keywords = list(config["keywords"])
    max_links = int(config.get("max_discovered_links_per_source", 25))

    docs = []
    for source in config["pages"]:
        docs.extend(fetch_page_source(source, keywords, max_links))
    for source in config["rss"]:
        docs.extend(fetch_rss_source(source, keywords))

    store.put_raw_documents(docs)
    items = extract_items_from_documents(docs, use_openai=True)
    saved = store.put_schedule_items(items)
    return {"raw_documents": len(docs), "extracted_items": len(items), "saved_items": saved}


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json; charset=utf-8", **CORS_HEADERS},
        "body": "" if status_code == 204 else json.dumps(body, ensure_ascii=False),
    }


def require_admin(event: dict[str, Any]) -> dict[str, Any]:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        groups = [group.strip() for group in groups.replace(",", " ").split() if group.strip()]
    admin_emails = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    email = str(claims.get("email") or "").strip().lower()
    if "calendar-admin" not in groups and email not in admin_emails:
        raise PermissionError("calendar-admin group is required")
    return claims


def admin_name(claims: dict[str, Any]) -> str:
    return str(claims.get("email") or claims.get("username") or claims.get("sub") or "")


def load_openai_secret_if_configured() -> None:
    secret_arn = os.getenv("OPENAI_SECRET_ARN", "").strip()
    if not secret_arn or os.getenv("OPENAI_API_KEY"):
        return
    try:
        import boto3
    except ImportError:
        return
    secret = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    secret_string = secret.get("SecretString", "")
    if not secret_string:
        return
    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError:
        os.environ["OPENAI_API_KEY"] = secret_string
        return
    if payload.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = str(payload["OPENAI_API_KEY"])
    if payload.get("OPENAI_MODEL"):
        os.environ["OPENAI_MODEL"] = str(payload["OPENAI_MODEL"])
