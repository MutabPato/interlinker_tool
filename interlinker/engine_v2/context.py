"""Corpus-level context shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence

from .text import document_frequencies, term_frequencies, tokenize
from .types import Page


@dataclass(frozen=True)
class CorpusContext:
    """Precomputed token statistics for the corpus."""

    title_tf: Dict[str, Dict[str, int]]
    body_tf: Dict[str, Dict[str, int]]
    title_df: Dict[str, int]
    body_df: Dict[str, int]
    avg_title_len: float
    avg_body_len: float
    page_map: Dict[str, Page]


def build_corpus_context(corpus: Sequence[Page]) -> CorpusContext:
    """Build token statistics for the provided corpus."""

    title_tf = {}
    body_tf = {}
    page_map = {}
    title_counters = []
    body_counters = []

    for page in corpus:
        page_map[page.url] = page
        title_tokens = tokenize(page.title)
        body_tokens = tokenize(page.text)
        title_counter = term_frequencies(title_tokens)
        body_counter = term_frequencies(body_tokens)
        title_tf[page.url] = dict(title_counter)
        body_tf[page.url] = dict(body_counter)
        title_counters.append(title_counter)
        body_counters.append(body_counter)

    title_df = document_frequencies(title_counters) if title_counters else {}
    body_df = document_frequencies(body_counters) if body_counters else {}
    if title_counters:
        total_title_tokens = sum(sum(counter.values()) for counter in title_counters)
        avg_title_len = total_title_tokens / len(title_counters)
    else:
        avg_title_len = 1.0

    if body_counters:
        total_body_tokens = sum(sum(counter.values()) for counter in body_counters)
        avg_body_len = total_body_tokens / len(body_counters)
    else:
        avg_body_len = 1.0

    return CorpusContext(
        title_tf=title_tf,
        body_tf=body_tf,
        title_df=title_df,
        body_df=body_df,
        avg_title_len=avg_title_len,
        avg_body_len=avg_body_len,
        page_map=page_map,
    )
