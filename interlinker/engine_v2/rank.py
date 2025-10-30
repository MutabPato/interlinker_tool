"""Scoring and ranking logic for engine v2."""

from __future__ import annotations

import math
from typing import Dict

from .config import EngineConfig


def logistic(x: float) -> float:
    """Compute the logistic function with safeguards against overflow."""

    return 1.0 / (1.0 + math.exp(-max(min(x, 60.0), -60.0)))


def score_candidate(features: Dict[str, float], config: EngineConfig) -> float:
    """Return a bounded score in [0, 1] for the candidate."""

    linear = 0.0
    for name, value in features.items():
        weight = config.feature_weight(name)
        linear += weight * value

    penalty = 0.0
    for name, value in features.items():
        penalty += config.penalty_weight(name) * value

    return logistic(linear - penalty)


def score_reason(features: Dict[str, float], config: EngineConfig, top_k: int = 2) -> str:
    """Return a human-friendly reason summary based on top weighted features."""

    weighted = []
    for name, value in features.items():
        weight = config.feature_weight(name)
        if weight > 0 and value > 0:
            weighted.append((weight * value, name, value))
    weighted.sort(reverse=True)

    fragments = []
    for _, name, value in weighted[:top_k]:
        fragments.append(_reason_fragment(name, value))
    return "; ".join(fragment for fragment in fragments if fragment)


def _reason_fragment(name: str, value: float) -> str:
    mapping = {
        "f_title_bm25": "strong title match",
        "f_body_bm25": "content overlap",
        "f_semantic": "semantic similarity",
        "f_entity_overlap": "shared entities",
        "f_tag_overlap": "tag overlap",
        "f_authority": "authoritative target",
        "f_click_depth": "shallow depth",
        "f_conversion_intent": "conversion intent",
        "f_freshness": "recent update",
        "f_lang_match": "language match",
        "f_quality": "high-quality target",
    }
    descriptor = mapping.get(name)
    if not descriptor:
        return ""
    if value >= 0.85:
        qualifier = "excellent"
    elif value >= 0.6:
        qualifier = "strong"
    else:
        qualifier = "good"
    return f"{qualifier} {descriptor}"
