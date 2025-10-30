"""Placement logic for selecting where to insert links."""

from __future__ import annotations

from typing import Dict

from .types import Page


def choose_placement(source: Page, target: Page, config: Dict[str, float]) -> str:
    """Return placement hint for the candidate suggestion."""

    metadata = target.metadata if isinstance(target.metadata, dict) else {}
    if metadata.get("is_pillar") or target.type in {"category", "pillar"}:
        return "intro"
    if metadata.get("is_conversion_page"):
        return "body"
    if metadata.get("is_reference"):
        return "conclusion"
    return "body"


def max_links_for_page(source: Page, config: Dict[str, float]) -> int:
    """Return the configured maximum links allowed for the page."""

    base = int(config.get("base_links_per_page", 3))
    words = max(len(source.text.split()), 1)
    extra = words // 500
    hard_cap = int(config.get("max_links_per_page", 12))
    return min(base + extra, hard_cap)
