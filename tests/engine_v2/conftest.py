"""Shared fixtures for engine v2 tests."""

from __future__ import annotations

from typing import Any, Dict, Iterable

import pytest

from interlinker.engine_v2.config import load_config
from interlinker.engine_v2.types import Page


@pytest.fixture()
def engine_config():
    """Provide a mutable copy of the default engine configuration."""

    return load_config(None)


def make_page(
    url: str,
    title: str,
    text: str,
    *,
    lang: str | None = "en",
    tags: Iterable[str] | None = None,
    type: str = "blog",
    metadata: Dict[str, Any] | None = None,
    published_at: str | None = "2024-01-01T00:00:00+00:00",
    noindex: bool = False,
    nofollow: bool = False,
) -> Page:
    return Page(
        url=url,
        title=title,
        html=text,
        text=text,
        lang=lang,
        tags=list(tags or []),
        type=type,
        published_at=published_at,
        canonical=url,
        noindex=noindex,
        nofollow=nofollow,
        metadata=metadata or {},
    )
