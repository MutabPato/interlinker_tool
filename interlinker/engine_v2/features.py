"""Feature extraction for candidate ranking."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Dict

from .context import CorpusContext
from .entities import entity_overlap
from .text import bm25, cosine_similarity, tokenize
from .types import Page

FeatureDict = Dict[str, float]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(min(value, maximum), minimum)


def _normalize(value: float, scale: float) -> float:
    if scale == 0:
        return 0.0
    return _clamp(value / scale)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def compute_features(
    source: Page,
    target: Page,
    context: CorpusContext,
    config: Dict[str, float],
) -> FeatureDict:
    """Compute normalized features for a (source, target) pairing."""

    total_docs = len(context.body_tf) or 1
    title_tf = Counter(context.title_tf.get(target.url, {}))
    body_tf = Counter(context.body_tf.get(target.url, {}))
    query_title_tokens = tokenize(source.title)
    query_body_tokens = tokenize(source.text)

    title_score = bm25(
        query_title_tokens,
        title_tf,
        sum(title_tf.values()) or 1,
        context.avg_title_len,
        context.title_df,
        total_docs,
    )
    body_score = bm25(
        query_body_tokens,
        body_tf,
        sum(body_tf.values()) or 1,
        context.avg_body_len,
        context.body_df,
        total_docs,
    )

    semantic = cosine_similarity(
        Counter(tokenize(source.text)),
        body_tf,
    )

    features: FeatureDict = {}
    features["f_title_bm25"] = _normalize(title_score, config.get("title_bm25_norm", 8.0))
    features["f_body_bm25"] = _normalize(body_score, config.get("body_bm25_norm", 12.0))
    features["f_semantic"] = _clamp(semantic)
    features["f_entity_overlap"] = _clamp(entity_overlap(source, target))

    source_tags = set(tag.lower() for tag in source.tags)
    target_tags = set(tag.lower() for tag in target.tags)
    if source_tags or target_tags:
        intersection = len(source_tags & target_tags)
        union = len(source_tags | target_tags) or 1
        features["f_tag_overlap"] = intersection / union
    else:
        features["f_tag_overlap"] = 0.0

    taxonomy_source = source.metadata.get("taxonomy", []) if isinstance(source.metadata, dict) else []
    taxonomy_target = target.metadata.get("taxonomy", []) if isinstance(target.metadata, dict) else []
    if taxonomy_source and taxonomy_target:
        overlap = len(set(taxonomy_source) & set(taxonomy_target))
        max_depth = max(len(taxonomy_source), len(taxonomy_target)) or 1
        features["f_taxonomy_distance"] = overlap / max_depth
    else:
        features["f_taxonomy_distance"] = 0.0

    authority = float(target.metadata.get("authority_score", 0.0)) if isinstance(target.metadata, dict) else 0.0
    if not authority:
        inlinks = float(target.metadata.get("inlinks", 0.0)) if isinstance(target.metadata, dict) else 0.0
        authority = inlinks / (config.get("max_inlinks", 50.0) or 50.0)
    features["f_authority"] = _clamp(authority)

    depth = target.metadata.get("click_depth") if isinstance(target.metadata, dict) else None
    if depth is None:
        depth = 3
    max_depth = config.get("max_click_depth", 6)
    features["f_click_depth"] = _clamp(1 - (depth - 1) / max_depth)

    features["f_conversion_intent"] = 1.0 if target.type in {"review", "category", "product"} else 0.3

    features["f_duplicate_risk"] = 1.0 if _already_links(source, target) else 0.0

    if source.lang and target.lang:
        features["f_lang_match"] = 1.0 if source.lang == target.lang else 0.3
    else:
        features["f_lang_match"] = 0.7

    features["f_lang_mismatch"] = 1 - features["f_lang_match"]

    features["f_quality"] = _clamp(_quality_score(target, config))

    features["f_freshness"] = _freshness_score(source, target, config)

    return features


def _already_links(source: Page, target: Page) -> bool:
    outbound = []
    if isinstance(source.metadata, dict):
        outbound = source.metadata.get("outbound_links", [])
    return target.url in outbound if outbound else False


def _quality_score(target: Page, config: Dict[str, float]) -> float:
    word_count = len(tokenize(target.text))
    normalized_wc = word_count / (config.get("quality_wordcount_norm", 800) or 800)
    content_score = 0.0
    if isinstance(target.metadata, dict):
        content_score = float(target.metadata.get("content_score", 0.0))
        schema = target.metadata.get("has_schema")
        if schema:
            content_score = max(content_score, 0.6)
    return _clamp(min(normalized_wc, 1.0) * 0.6 + content_score * 0.4)


def _freshness_score(source: Page, target: Page, config: Dict[str, float]) -> float:
    source_ts = _parse_timestamp(source.published_at)
    target_ts = _parse_timestamp(target.published_at)
    if not target_ts:
        return 0.4
    if not source_ts:
        source_ts = datetime.now(timezone.utc)
    delta_days = abs((source_ts - target_ts).days)
    freshness_window = config.get("freshness_half_life_days", 90)
    return _clamp(max(0.1, 1 - delta_days / (freshness_window * 2)))
