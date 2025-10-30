"""Anchor text extraction and selection."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .entities import first_matching_entity
from .types import Anchor, Page

_STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "a",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "an",
    "be",
    "is",
}

_VARIANT_PRIORITY = {
    "entity": 1.0,
    "exact": 0.95,
    "partial": 0.8,
    "brand": 0.75,
    "tag": 0.7,
    "generic": 0.6,
}


def extract_candidate_anchors(source: Page, target: Page, config: Dict[str, float]) -> List[Anchor]:
    """Return raw anchor candidates for the target within the source text."""

    phrases = set()
    title = target.title.strip()
    if title:
        phrases.add((title, "exact"))
        head_terms = _head_terms(title)
        if head_terms:
            phrases.add((head_terms, "partial"))
        tail_terms = _tail_terms(title)
        if tail_terms:
            phrases.add((tail_terms, "partial"))

    entity_match = first_matching_entity(source, target)
    if entity_match:
        phrases.add((entity_match[0], entity_match[1] if entity_match[1] in _VARIANT_PRIORITY else "entity"))

    metadata = target.metadata if isinstance(target.metadata, dict) else {}
    for term in metadata.get("head_terms", []):
        phrases.add((term, "partial"))
    brand = metadata.get("brand")
    if brand:
        phrases.add((brand, "brand"))

    for tag in target.tags:
        candidate = str(tag).strip()
        if not candidate:
            continue
        lowered_candidate = candidate.lower()
        title_lower = target.title.lower()
        body_lower = target.text.lower()
        if lowered_candidate not in title_lower and lowered_candidate not in body_lower:
            continue
        phrases.add((candidate.replace("-", " "), "tag"))

    normalized_phrases = set()
    for phrase, variant in phrases:
        cleaned = phrase.strip()
        if not cleaned:
            continue
        if not _valid_phrase(cleaned, variant):
            continue
        normalized_phrases.add((cleaned, variant))

    phrases = normalized_phrases

    if not phrases:
        return []

    lowered = source.text.lower()
    anchors: List[Anchor] = []
    for phrase, variant in phrases:
        pattern = re.escape(phrase.lower())
        for match in re.finditer(pattern, lowered):
            start, end = match.span()
            actual_text = source.text[start:end]
            if not _valid_anchor_text(actual_text, variant):
                continue
            anchors.append(Anchor(text=actual_text, start=start, end=end, variant=variant))
    return anchors


def select_anchors(
    source: Page,
    target: Page,
    anchors: List[Anchor],
    config: Dict[str, float],
) -> List[Anchor]:
    """Filter and diversify anchors according to heuristics."""

    if not anchors:
        return []

    limit = int(config.get("max_anchors_per_target", 2))
    text_length = max(len(source.text), 1)

    scored: Dict[Tuple[int, int], Tuple[float, Anchor]] = {}
    for anchor in anchors:
        score = _anchor_score(anchor, text_length)
        key = (anchor.start, anchor.end)
        if key not in scored or score > scored[key][0]:
            scored[key] = (score, anchor)

    ranked = sorted(scored.values(), key=lambda item: item[0], reverse=True)
    selected: List[Anchor] = []
    exact_allowed = max(1, int(limit * 0.4))
    exact_count = 0
    used_texts = set()

    for _, anchor in ranked:
        if len(selected) >= limit:
            break
        normalized_text = anchor.text.strip().lower()
        if normalized_text in used_texts:
            continue
        if anchor.variant == "exact" and exact_count >= exact_allowed:
            continue
        selected.append(anchor)
        used_texts.add(normalized_text)
        if anchor.variant == "exact":
            exact_count += 1

    # Ensure diversity: if all anchors share the same variant, try to add another variant when possible.
    if len(selected) < limit:
        selected_variants = {anchor.variant for anchor in selected}
        for _, anchor in ranked:
            if len(selected) >= limit:
                break
            if anchor in selected or anchor.variant in selected_variants:
                continue
            normalized_text = anchor.text.strip().lower()
            if normalized_text in used_texts:
                continue
            selected.append(anchor)
            used_texts.add(normalized_text)
            selected_variants.add(anchor.variant)

    # Sort anchors by their position in the source text for deterministic output.
    selected.sort(key=lambda anchor: anchor.start)
    return selected


def _valid_phrase(phrase: str, variant: str) -> bool:
    words = phrase.split()
    if variant in {"entity", "brand", "tag"}:
        return 1 <= len(words) <= 5
    return 1 < len(words) <= 7


def _valid_anchor_text(text: str, variant: str) -> bool:
    words = [word for word in re.split(r"\s+", text.strip()) if word]
    if variant in {"entity", "brand", "tag"}:
        if len(words) != 1:
            return False
        return words[0].lower() not in _STOPWORDS
    if len(words) < 2 or len(words) > 7:
        return False
    if all(word.lower() in _STOPWORDS for word in words):
        return False
    return True


def _head_terms(title: str) -> str:
    words = title.split()
    if len(words) <= 4:
        return title
    return " ".join(words[:4])


def _tail_terms(title: str) -> str:
    words = title.split()
    if len(words) <= 4:
        return title
    return " ".join(words[-3:])


def _anchor_score(anchor: Anchor, text_length: int) -> float:
    variant_weight = _VARIANT_PRIORITY.get(anchor.variant, 0.5)
    position_factor = 1 - (anchor.start / text_length)
    length = len(anchor.text.split())
    length_factor = max(0.0, 1 - abs(length - 4) / 10)
    return variant_weight * (0.7 + 0.2 * position_factor + 0.1 * length_factor)
