from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote_plus


def build_search_links(query: str) -> dict[str, str]:
    encoded = quote_plus(query)
    return {
        "google": f"https://www.google.com/search?q={encoded}&tbs=qdr%3Ad",
        "x": f"https://x.com/search?q={encoded}&src=typed_query&f=live",
        "instagram": f"https://www.instagram.com/explore/search/keyword/?q={encoded}",
        "tiktok": f"https://www.tiktok.com/search?q={encoded}",
    }


def write_checklist(queries: list[str], output_dir: Path = Path("outputs")) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"manual_checklist_{date.today().isoformat()}.md"
    lines = [
        "# Pom Pom Purin Manual Check Checklist",
        "",
        "SNSや検索結果で見つけたURLは samples/manual_items.csv と同じ列でCSV化し、import-manualで取り込んでください。",
        "",
    ]
    for query in queries:
        lines.append(f"## {query}")
        for label, url in build_search_links(query).items():
            lines.append(f"- {label}: {url}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

