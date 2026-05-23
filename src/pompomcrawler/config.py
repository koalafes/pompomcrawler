from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path("config/sources.yml")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to read config/sources.yml. "
            "Install dependencies with: python3 -m pip install -e ."
        ) from exc

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    loaded.setdefault("keywords", [])
    loaded.setdefault("pages", [])
    loaded.setdefault("rss", [])
    loaded.setdefault("checklist_queries", [])
    loaded.setdefault("max_discovered_links_per_source", 25)
    return loaded

