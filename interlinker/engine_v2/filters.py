"""Guardrails and filtering for engine v2 candidates."""

from __future__ import annotations

from typing import Dict

from .text import tokenize
from .types import Page


def allow_candidate(source: Page, target: Page, config: Dict[str, float]) -> bool:
    """Return True when the target is safe to consider."""

    if target.url == source.url:
        return False
    if target.noindex or target.nofollow:
        return False
    if target.canonical and target.canonical != target.url:
        return False
    metadata = target.metadata if isinstance(target.metadata, dict) else {}
    if metadata.get("is_redirect"):
        return False
    status = int(metadata.get("status_code", 200))
    if status >= 300:
        return False
    if metadata.get("is_paginated_duplicate"):
        return False
    if "login" in target.url or "cart" in target.url:
        return False
    if metadata.get("blocked"):
        return False

    # Language guardrail: block hard mismatch unless bilingual override.
    if source.lang and target.lang and source.lang != target.lang:
        bilingual_tags = set(tag.lower() for tag in source.tags) & set(tag.lower() for tag in target.tags)
        if not bilingual_tags:
            return config.get("allow_cross_language", False)
    return True


def risk_flags(source: Page, target: Page, config: Dict[str, float]) -> Dict[str, bool]:
    """Return guardrail flags for the (source, target) pair."""

    flags: Dict[str, bool] = {}

    if source.lang and target.lang and source.lang != target.lang:
        flags["lang_mismatch"] = True

    if target.type == "product":
        word_count = len(tokenize(target.text))
        flags["thin_target"] = word_count < config.get("product_wordcount_min", 250)

    outbound = []
    if isinstance(source.metadata, dict):
        outbound = source.metadata.get("outbound_links", [])
    if outbound and target.url in outbound:
        flags["dup_anchor"] = True

    return flags
