"""Configuration helpers for engine v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class EngineConfig:
    """Typed wrapper around the engine configuration dictionary."""

    raw: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def feature_weight(self, feature: str) -> float:
        weights = self.raw.get("weights", {})
        return weights.get(feature, 0.0)

    def penalty_weight(self, feature: str) -> float:
        penalties = self.raw.get("penalties", {})
        return penalties.get(feature, 0.0)


DEFAULTS: Dict[str, Any] = {
    "max_candidates": 120,
    "base_links_per_page": 3,
    "max_links_per_page": 12,
    "max_anchors_per_target": 2,
    "weights": {
        "f_title_bm25": 1.4,
        "f_body_bm25": 1.1,
        "f_semantic": 1.2,
        "f_entity_overlap": 1.5,
        "f_tag_overlap": 0.9,
        "f_taxonomy_distance": 0.7,
        "f_authority": 0.8,
        "f_click_depth": 0.7,
        "f_conversion_intent": 0.6,
        "f_freshness": 0.4,
        "f_lang_match": 0.5,
        "f_quality": 0.8,
    },
    "penalties": {
        "f_duplicate_risk": 2.5,
        "f_lang_mismatch": 1.0,
    },
}


def load_config(path: str | Path | None = None) -> EngineConfig:
    """Load configuration from YAML, merging with defaults."""

    data: Dict[str, Any] = DEFAULTS.copy()
    data["weights"] = dict(DEFAULTS["weights"])
    data["penalties"] = dict(DEFAULTS["penalties"])

    if path is not None and Path(path).exists():
        with Path(path).open("r", encoding="utf-8") as stream:
            user = yaml.safe_load(stream) or {}
        merge_into(data, user)

    return EngineConfig(data)


def merge_into(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Recursively merge override into base dict."""

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_into(base[key], value)
        else:
            base[key] = value
