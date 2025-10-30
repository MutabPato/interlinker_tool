"""Coordinator for the engine v2 linking pipeline."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from . import anchors as anchors_module
from . import candidates as candidates_module
from . import features as features_module
from . import filters as filters_module
from . import placement as placement_module
from . import rank as rank_module
from .config import EngineConfig, load_config
from .context import CorpusContext, build_corpus_context
from .types import Anchor, Page, Suggestion


@dataclass(frozen=True)
class PipelineContext:
    """Aggregated state for orchestrating a linking pass."""

    corpus_context: CorpusContext
    config: EngineConfig


def suggest_links(
    page: Page,
    corpus: Sequence[Page],
    config: EngineConfig | None = None,
) -> List[Suggestion]:
    """Return ordered link suggestions for the given page."""

    engine_config = config or load_config(None)
    corpus_context = build_corpus_context(corpus)
    pipe_context = PipelineContext(corpus_context=corpus_context, config=engine_config)

    raw_candidates = candidates_module.generate_candidates(
        page,
        corpus,
        corpus_context,
        engine_config.raw,
    )

    suggestions, _ = _evaluate_candidates(page, raw_candidates, pipe_context)
    return suggestions


def _evaluate_candidates(
    source: Page,
    candidates: Sequence[Page],
    pipe_context: PipelineContext,
) -> tuple[List[Suggestion], List[Dict[str, object]]]:
    config = pipe_context.config
    corpus_context = pipe_context.corpus_context

    evaluated: List[Dict[str, object]] = []
    for target in candidates:
        if not filters_module.allow_candidate(source, target, config.raw):
            continue

        features = features_module.compute_features(source, target, corpus_context, config.raw)
        score = rank_module.score_candidate(features, config)
        if score < config.get("score_floor", 0.4):
            continue
        anchor_options = anchors_module.extract_candidate_anchors(source, target, config.raw)
        selected_anchors = anchors_module.select_anchors(source, target, anchor_options, config.raw)
        if not selected_anchors:
            continue
        risk_map = filters_module.risk_flags(source, target, config.raw)
        if risk_map.get("lang_mismatch") and features.get("f_semantic", 0.0) < 0.18:
            continue

        placement_hint = placement_module.choose_placement(source, target, config.raw)
        reason = rank_module.score_reason(features, config)
        evaluated.append(
            {
                "target": target,
                "features": features,
                "score": score,
                "anchors": selected_anchors,
                "risk_flags": [flag for flag, value in risk_map.items() if value],
                "placement": placement_hint,
                "reason": reason,
                "role": _candidate_role(source, target),
            }
        )

    evaluated.sort(key=lambda item: item["score"], reverse=True)
    link_budget = placement_module.max_links_for_page(source, config.raw)
    selected: List[Suggestion] = []
    selected_roles: set[str] = set()
    used_targets: set[str] = set()
    used_anchor_texts: set[str] = set()

    sibling_candidates = [item for item in evaluated if item["role"] == "sibling"].copy()
    parent_candidates = [item for item in evaluated if item["role"] == "parent"].copy()

    for item in evaluated:
        if len(selected) >= link_budget:
            break
        target: Page = item["target"]  # type: ignore[assignment]
        if target.url in used_targets:
            continue
        if _conflicts_with_existing(item["anchors"], used_anchor_texts):
            continue
        suggestion = Suggestion(
            target_url=target.url,
            reason=item["reason"],
            score=float(item["score"]),
            anchors=list(item["anchors"]),
            placement_hint=item["placement"],
            rel="follow",
            risk_flags=list(item["risk_flags"]),
        )
        selected.append(suggestion)
        used_targets.add(target.url)
        used_anchor_texts.update(anchor.text.lower() for anchor in suggestion.anchors)
        selected_roles.add(item["role"])  # type: ignore[arg-type]

    selected = _ensure_hub_and_sibling(
        selected,
        sibling_candidates,
        parent_candidates,
        link_budget,
        used_targets,
        used_anchor_texts,
        selected_roles,
    )
    selected.sort(key=lambda item: item.score, reverse=True)
    return selected, evaluated


def dry_run(
    pages: Sequence[Page],
    corpus: Sequence[Page],
    config: EngineConfig | None = None,
) -> Dict[str, float | Dict[str, float]]:
    """Return diagnostic metrics for a batch of pages."""

    engine_config = config or load_config(None)
    corpus_context = build_corpus_context(corpus)
    pipe_context = PipelineContext(corpus_context=corpus_context, config=engine_config)

    total_pages = len(pages) or 1
    pages_with_suggestions = 0
    inbound_counts: Dict[str, int] = {page.url: 0 for page in corpus}
    anchor_variants = Counter()
    selected_scores: List[float] = []
    rejected_scores: List[float] = []
    duplicate_targets = 0
    lang_mismatch_suggestions = 0
    total_suggestions = 0

    for page in pages:
        raw_candidates = candidates_module.generate_candidates(
            page,
            corpus,
            corpus_context,
            engine_config.raw,
        )
        suggestions, evaluated = _evaluate_candidates(page, raw_candidates, pipe_context)

        if suggestions:
            pages_with_suggestions += 1

        seen_targets: set[str] = set()
        selected_urls = {suggestion.target_url for suggestion in suggestions}

        for suggestion in suggestions:
            total_suggestions += 1
            selected_scores.append(suggestion.score)
            inbound_counts[suggestion.target_url] = inbound_counts.get(suggestion.target_url, 0) + 1
            for anchor in suggestion.anchors:
                anchor_variants[anchor.variant] += 1
            if "lang_mismatch" in suggestion.risk_flags:
                lang_mismatch_suggestions += 1
            if suggestion.target_url in seen_targets:
                duplicate_targets += 1
            seen_targets.add(suggestion.target_url)

        for item in evaluated:
            if item["target"].url not in selected_urls:  # type: ignore[union-attr]
                rejected_scores.append(float(item["score"]))

    coverage = pages_with_suggestions / total_pages
    orphan_rate = _compute_orphan_rate(inbound_counts)
    avg_click_depth_after = _simulate_click_depth(corpus, inbound_counts)
    anchor_diversity = _shannon_entropy(anchor_variants)
    mean_score_selected = sum(selected_scores) / len(selected_scores) if selected_scores else 0.0
    mean_score_rejected = sum(rejected_scores) / len(rejected_scores) if rejected_scores else 0.0
    language_mismatch_rate = lang_mismatch_suggestions / total_suggestions if total_suggestions else 0.0
    dup_target_rate = duplicate_targets / total_pages

    return {
        "coverage": coverage,
        "orphan_rate": orphan_rate,
        "avg_click_depth_after": avg_click_depth_after,
        "anchor_diversity_index": anchor_diversity,
        "dup_target_rate": dup_target_rate,
        "mean_score_selected": mean_score_selected,
        "mean_score_rejected": mean_score_rejected,
        "language_mismatch_rate": language_mismatch_rate,
        "anchor_variant_counts": dict(anchor_variants),
    }


def _conflicts_with_existing(anchors: Iterable[Anchor], used_texts: set[str]) -> bool:
    for anchor in anchors:
        if anchor.text.lower() in used_texts:
            return True
    return False


def _candidate_role(source: Page, target: Page) -> str:
    if _is_parent(source, target):
        return "parent"
    if _is_sibling(source, target):
        return "sibling"
    metadata = target.metadata if isinstance(target.metadata, dict) else {}
    if metadata.get("is_money_page"):
        return "money"
    return "other"


def _safe_meta(page: Page) -> Dict[str, object]:
    return page.metadata if isinstance(page.metadata, dict) else {}


def _is_sibling(source: Page, target: Page) -> bool:
    if source.url == target.url:
        return False
    source_meta = _safe_meta(source)
    target_meta = _safe_meta(target)
    parent_source = source_meta.get("parent_id")
    parent_target = target_meta.get("parent_id")
    if parent_source and parent_target and parent_source == parent_target:
        return True
    return bool(set(source.tags) & set(target.tags)) and source.type == target.type


def _is_parent(source: Page, target: Page) -> bool:
    target_meta = _safe_meta(target)
    if target_meta.get("is_pillar") or target_meta.get("is_hub"):
        return True
    source_tax = _safe_meta(source).get("taxonomy", [])
    target_tax = target_meta.get("taxonomy", [])
    if isinstance(source_tax, list) and isinstance(target_tax, list) and target_tax:
        return source_tax[: len(target_tax)] == target_tax
    return False


def _ensure_hub_and_sibling(
    selected: List[Suggestion],
    sibling_candidates: List[Dict[str, object]],
    parent_candidates: List[Dict[str, object]],
    limit: int,
    used_targets: set[str],
    used_anchor_texts: set[str],
    selected_roles: set[str],
) -> List[Suggestion]:
    result = list(selected)
    has_sibling = "sibling" in selected_roles
    has_parent = "parent" in selected_roles

    if not has_parent:
        for item in parent_candidates:
            target: Page = item["target"]  # type: ignore[assignment]
            if target.url in used_targets:
                continue
            if _conflicts_with_existing(item["anchors"], used_anchor_texts):
                continue
            suggestion = Suggestion(
                target_url=target.url,
                reason=item["reason"],
                score=float(item["score"]),
                anchors=list(item["anchors"]),
                placement_hint=item["placement"],
                rel="follow",
                risk_flags=list(item["risk_flags"]),
            )
            result = _insert_or_replace(result, suggestion, limit)
            used_targets.add(target.url)
            used_anchor_texts.update(anchor.text.lower() for anchor in suggestion.anchors)
            selected_roles.add("parent")
            break

    if not has_sibling:
        for item in sibling_candidates:
            target: Page = item["target"]  # type: ignore[assignment]
            if target.url in used_targets:
                continue
            if _conflicts_with_existing(item["anchors"], used_anchor_texts):
                continue
            suggestion = Suggestion(
                target_url=target.url,
                reason=item["reason"],
                score=float(item["score"]),
                anchors=list(item["anchors"]),
                placement_hint=item["placement"],
                rel="follow",
                risk_flags=list(item["risk_flags"]),
            )
            result = _insert_or_replace(result, suggestion, limit)
            used_targets.add(target.url)
            used_anchor_texts.update(anchor.text.lower() for anchor in suggestion.anchors)
            selected_roles.add("sibling")
            break

    return result[:limit]


def _insert_or_replace(existing: List[Suggestion], new_item: Suggestion, limit: int) -> List[Suggestion]:
    if len(existing) < limit:
        existing.append(new_item)
        return existing
    lowest_index = min(range(len(existing)), key=lambda idx: existing[idx].score)
    if existing[lowest_index].score < new_item.score:
        existing[lowest_index] = new_item
    return existing


def _compute_orphan_rate(inbound_counts: Dict[str, int]) -> float:
    total = len(inbound_counts) or 1
    orphans = sum(1 for count in inbound_counts.values() if count == 0)
    return orphans / total


def _simulate_click_depth(corpus: Sequence[Page], inbound_counts: Dict[str, int]) -> float:
    if not corpus:
        return 0.0
    total_depth = 0.0
    for page in corpus:
        metadata = _safe_meta(page)
        depth = float(metadata.get("click_depth", 3.0))
        inbound = inbound_counts.get(page.url, 0)
        if inbound:
            depth = max(1.0, depth - 0.5 * inbound)
        total_depth += depth
    return total_depth / len(corpus)


def _shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    if len(counter) <= 1:
        return 0.0
    return entropy / math.log(len(counter))
