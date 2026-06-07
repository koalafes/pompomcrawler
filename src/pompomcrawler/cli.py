from __future__ import annotations

import argparse
from pathlib import Path

from .checklist import write_checklist
from .config import DEFAULT_CONFIG, load_config
from .exporter import export_schedule
from .extract import extract_items_from_documents
from .fetchers import fetch_page_source, fetch_rss_source
from .html_calendar import export_calendar_html
from .dynamodb_store import DynamoScheduleStore
from .manual import import_manual_csv
from .storage import (
    append_raw_documents,
    append_schedule_items,
    read_raw_documents,
    read_schedule_items,
    schedule_source_urls,
    write_schedule_items,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pompomcrawler")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to sources.yml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("crawl", help="Crawl configured public pages and RSS feeds")
    subparsers.add_parser("make-checklist", help="Write manual Google/SNS check links")
    import_parser = subparsers.add_parser("import-manual", help="Import manually found URLs/items from CSV")
    import_parser.add_argument("csv_path", help="Manual CSV path")
    extract_parser = subparsers.add_parser("extract", help="Extract schedule candidates from raw documents")
    extract_parser.add_argument("--limit", type=int, default=0, help="Maximum raw documents to process")
    extract_parser.add_argument("--last", type=int, default=0, help="Process only the most recent N raw documents")
    extract_parser.add_argument("--no-openai", action="store_true", help="Use heuristic extraction even if OPENAI_API_KEY is set")
    extract_parser.add_argument("--replace", action="store_true", help="Replace stored schedule items instead of appending")
    extract_parser.add_argument("--reprocess", action="store_true", help="Reprocess raw documents that already have schedule items")
    export_parser = subparsers.add_parser("export", help="Export merged schedule CSV/XLSX/HTML")
    export_parser.add_argument("--all-history", action="store_true", help="Include old past items instead of the default recent/future window")
    export_parser.add_argument("--past-days", type=int, default=30, help="Past days to include when filtering schedule output")
    html_parser = subparsers.add_parser("export-html", help="Export merged schedule as an HTML calendar")
    html_parser.add_argument("--all-history", action="store_true", help="Include old past items instead of the default recent/future window")
    html_parser.add_argument("--past-days", type=int, default=30, help="Past days to include when filtering calendar output")
    html_parser.add_argument("--output-dir", default="outputs", help="Directory for generated HTML")
    html_parser.add_argument("--filename", default="pompompurin_calendar.html", help="Generated HTML filename")
    html_parser.add_argument("--aws-runtime", action="store_true", help="Load schedule items from AWS API instead of embedding local data")
    html_parser.add_argument("--admin", action="store_true", help="Generate the Cognito-protected admin calendar page")
    subparsers.add_parser("migrate-aws", help="Migrate local JSONL data to AWS DynamoDB tables")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "crawl":
        config = load_config(args.config)
        keywords = list(config["keywords"])
        max_links = int(config.get("max_discovered_links_per_source", 25))
        docs = []
        for source in config["pages"]:
            docs.extend(fetch_page_source(source, keywords, max_links))
        for source in config["rss"]:
            docs.extend(fetch_rss_source(source, keywords))
        count = append_raw_documents(docs)
        print(f"Saved {count} raw documents.")
        return 0

    if args.command == "make-checklist":
        config = load_config(args.config)
        path = write_checklist(list(config["checklist_queries"]))
        print(f"Wrote checklist: {path}")
        return 0

    if args.command == "import-manual":
        docs = import_manual_csv(Path(args.csv_path))
        count = append_raw_documents(docs)
        print(f"Imported {count} manual documents.")
        return 0

    if args.command == "extract":
        docs = read_raw_documents()
        if args.last:
            docs = docs[-args.last :]
        elif args.limit:
            docs = docs[: args.limit]
        selected_count = len(docs)
        if not args.replace and not args.reprocess:
            processed_urls = schedule_source_urls(read_schedule_items())
            docs = [doc for doc in docs if doc.url not in processed_urls]
        if not docs:
            if selected_count:
                print(f"No unprocessed raw documents found in {selected_count} selected documents.")
            else:
                print("No raw documents found.")
            return 0
        items = extract_items_from_documents(docs, use_openai=not args.no_openai)
        count = write_schedule_items(items) if args.replace else append_schedule_items(items)
        print(f"Processed {len(docs)} raw documents; saved {count} new schedule items.")
        return 0

    if args.command == "export":
        items = read_schedule_items()
        csv_path, xlsx_path, html_path = export_schedule(
            items,
            filter_window=not args.all_history,
            past_days=args.past_days,
        )
        print(f"Wrote CSV: {csv_path}")
        if xlsx_path:
            print(f"Wrote XLSX: {xlsx_path}")
        else:
            print("openpyxl is not installed; skipped XLSX export.")
        print(f"Wrote HTML: {html_path}")
        return 0

    if args.command == "export-html":
        items = read_schedule_items()
        html_path = export_calendar_html(
            items,
            Path(args.output_dir),
            filter_window=not args.all_history,
            past_days=args.past_days,
            aws_runtime=args.aws_runtime,
            filename=args.filename,
            admin_mode=args.admin,
        )
        print(f"Wrote HTML: {html_path}")
        return 0

    if args.command == "migrate-aws":
        store = DynamoScheduleStore.from_env()
        raw_count = store.put_raw_documents(read_raw_documents())
        item_count = store.put_schedule_items(read_schedule_items())
        print(f"Migrated raw documents: {raw_count}")
        print(f"Migrated schedule items: {item_count}")
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
