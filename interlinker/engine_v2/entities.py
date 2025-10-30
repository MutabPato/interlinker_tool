"""Entity extraction helpers with lightweight heuristics."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .types import Page

ENTITY_TYPES = ("product", "brand", "category", "generic")

_CAPITALIZED_RE = re.compile(r"\b([A-Z][a-zA-Z0-9\-']+(?:\s+[A-Z][a-zA-Z0-9\-']+)*)\b")


def get_entities(page: Page) -> List[Dict[str, str]]:
    """Return entity dictionaries for the page."""

    metadata_entities = page.metadata.get("entities") if isinstance(page.metadata, dict) else None
    if isinstance(metadata_entities, list) and metadata_entities:
        formatted = []
        for entity in metadata_entities:
            if isinstance(entity, dict) and "name" in entity:
                etype = entity.get("type", "generic")
                formatted.append({"name": entity["name"], "type": etype})
        if formatted:
            return formatted

    inferred = []
    for match in _CAPITALIZED_RE.findall(page.text):
        clean = match.strip()
        if len(clean.split()) > 6:
            continue
        inferred.append({"name": clean, "type": "generic"})
    return inferred


def entity_overlap(source: Page, target: Page) -> float:
    """Return weighted overlap between source and target entities."""

    source_entities = get_entities(source)
    target_entities = get_entities(target)
    if not source_entities or not target_entities:
        return 0.0

    weight_map = {"product": 1.0, "brand": 0.8, "category": 0.6, "generic": 0.3}
    total_weight = 0.0
    matched_weight = 0.0

    target_values = {
        entity["name"].lower(): weight_map.get(entity.get("type", "generic"), 0.3)
        for entity in target_entities
    }

    for entity in source_entities:
        name = entity["name"].lower()
        weight = weight_map.get(entity.get("type", "generic"), 0.3)
        total_weight += weight
        if name in target_values:
            matched_weight += max(weight, target_values[name])

    if total_weight == 0:
        return 0.0
    return min(matched_weight / total_weight, 1.0)


def first_matching_entity(source: Page, target: Page) -> Tuple[str, str] | None:
    """Return the first overlapping entity with its type if available."""

    source_entities = get_entities(source)
    target_entities = get_entities(target)
    lookup = {entity["name"].lower(): entity.get("type", "generic") for entity in target_entities}
    for entity in source_entities:
        name = entity["name"].lower()
        if name in lookup:
            return entity["name"], lookup[name]
    return None
