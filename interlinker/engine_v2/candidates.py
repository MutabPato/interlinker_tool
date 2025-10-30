"""Candidate generation strategies for engine v2."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Sequence, Tuple
from urllib.parse import parse_qsl, urlparse

from .context import CorpusContext
from .entities import entity_overlap
from .text import bm25, cosine_similarity, term_frequencies, tokenize
from .types import Page


def _business_filter(source: Page, target: Page) -> bool:
    if target.url == source.url:
        return False
    if target.noindex or target.nofollow:
        return False
    if target.canonical and source.canonical and target.canonical == source.canonical:
        return False
    if target.metadata.get("is_login") or target.metadata.get("is_cart"):
        return False
    status = int(target.metadata.get("status_code", 200))
    if status >= 300:
        return False
    if "?" in target.url:
        query = urlparse(target.url).query
        params = [name.lower() for name, _ in parse_qsl(query)]
        if all(param.startswith("utm") or param.startswith("ref") or param == "replytocom" for param in params):
            return False
    return True


def _language_factor(source: Page, target: Page) -> float:
    if not source.lang or not target.lang:
        return 0.7
    if source.lang == target.lang:
        return 1.0
    bilingual_tags = set(tag.lower() for tag in source.tags) & set(tag.lower() for tag in target.tags)
    return 0.6 if bilingual_tags else 0.1


def _prefer_review_targets(source: Page, target: Page) -> float:
    if source.type != "review":
        return 1.0
    title_lower = target.title.lower()
    if target.type in {"category", "review"} and any(keyword in title_lower for keyword in ("best", "top", "guide")):
        return 1.2
    if target.type == "product":
        return 1.1
    return 1.0


def _compute_tag_overlap(source: Page, target: Page) -> float:
    source_tags = {tag.lower() for tag in source.tags}
    target_tags = {tag.lower() for tag in target.tags}
    if not source_tags or not target_tags:
        return 0.0
    intersection = len(source_tags & target_tags)
    union = len(source_tags | target_tags)
    return intersection / union if union else 0.0


def generate_candidates(
    source: Page,
    corpus: Sequence[Page],
    context: CorpusContext,
    config: Dict[str, float],
) -> List[Page]:
    """Return a recall-oriented list of candidate target pages for the source."""

    scored: List[Tuple[float, Page]] = []
    query_title_tokens = tokenize(source.title)
    query_body_tokens = tokenize(source.text)
    query_body_tf = term_frequencies(query_body_tokens)

    total_docs = len(corpus) or 1

    for candidate in corpus:
        if not _business_filter(source, candidate):
            continue

        title_tf_dict = context.title_tf.get(candidate.url, {})
        body_tf_dict = context.body_tf.get(candidate.url, {})
        title_tf = Counter(title_tf_dict)
        body_tf = Counter(body_tf_dict)
        title_length = sum(title_tf.values()) or 1
        body_length = sum(body_tf.values()) or 1

        title_score = bm25(
            query_title_tokens,
            title_tf,
            title_length,
            context.avg_title_len,
            context.title_df,
            total_docs,
        )
        body_score = bm25(
            query_body_tokens,
            body_tf,
            body_length,
            context.avg_body_len,
            context.body_df,
            total_docs,
        )

        semantic = cosine_similarity(query_body_tf, body_tf)
        entity_score = entity_overlap(source, candidate)
        tag_overlap = _compute_tag_overlap(source, candidate)
        lang_factor = _language_factor(source, candidate)

        recall_score = (
            0.35 * min(title_score / 8.0, 1.0)
            + 0.35 * min(body_score / 12.0, 1.0)
            + 0.2 * semantic
            + 0.25 * entity_score
            + 0.15 * tag_overlap
        )
        recall_score *= lang_factor * _prefer_review_targets(source, candidate)

        if recall_score <= 0.05:
            continue
        scored.append((recall_score, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    limit = int(config.get("max_candidates", 50))
    return [page for _, page in scored[:limit]]
