"""Shared text utilities for engine v2."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence

_TOKEN_RE = re.compile(r"[\w']+")


def tokenize(text: str) -> List[str]:
    """Return lower-cased word tokens from the provided text."""

    return [token.lower() for token in _TOKEN_RE.findall(text)]


def term_frequencies(tokens: Iterable[str]) -> Counter[str]:
    """Return term frequencies for the tokens."""

    return Counter(tokens)


def document_frequencies(documents: Sequence[Counter[str]]) -> Dict[str, int]:
    """Compute document frequencies for the token counters."""

    df: Dict[str, int] = {}
    for doc in documents:
        for term in doc:
            df[term] = df.get(term, 0) + 1
    return df


def bm25(
    query_tokens: Sequence[str],
    document_tf: Counter[str],
    document_length: int,
    avg_doc_length: float,
    df: Dict[str, int],
    total_docs: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Compute BM25 score for the query and document."""

    score = 0.0
    for term in query_tokens:
        if term not in document_tf:
            continue
        freq = document_tf[term]
        idf = math.log(1 + (total_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
        denom = freq + k1 * (1 - b + b * document_length / (avg_doc_length or 1.0))
        score += idf * freq * (k1 + 1) / denom
    return score


def cosine_similarity(counter_a: Counter[str], counter_b: Counter[str]) -> float:
    """Cosine similarity between two sparse term-frequency counters."""

    if not counter_a or not counter_b:
        return 0.0
    dot = sum(counter_a[term] * counter_b.get(term, 0) for term in counter_a)
    norm_a = math.sqrt(sum(value * value for value in counter_a.values()))
    norm_b = math.sqrt(sum(value * value for value in counter_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def jaccard(set_a: Iterable[str], set_b: Iterable[str]) -> float:
    """Return Jaccard similarity for two iterables."""

    set_a = set(set_a)
    set_b = set(set_b)
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    if not union:
        return 0.0
    return len(intersection) / len(union)
