"""Typed data structures used by the engine v2 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Anchor:
    """Represents a deterministic anchor text placement within the source text."""

    text: str
    start: int
    end: int
    variant: str


@dataclass(frozen=True)
class Suggestion:
    """Suggested internal link for a given source page."""

    target_url: str
    reason: str
    score: float
    anchors: List[Anchor]
    placement_hint: str
    rel: str
    risk_flags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    """Candidate target page considered for linking."""

    page: "Page"
    features: Dict[str, float]
    score: float
    anchors: List[Anchor]
    risk_flags: List[str]
    placement_hint: str


@dataclass(frozen=True)
class Page:
    """Normalized page representation for the linking engine."""

    url: str
    title: str
    html: str
    text: str
    lang: Optional[str]
    tags: List[str]
    type: str
    published_at: Optional[str]
    canonical: Optional[str]
    noindex: bool
    nofollow: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
