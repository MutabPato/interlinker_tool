"""Guardrail enforcement tests."""

from __future__ import annotations

from interlinker.engine_v2.index import suggest_links

from .conftest import make_page


def test_guardrails_exclude_risky_targets(engine_config):
    source = make_page(
        url="https://example.com/blog/acme",
        title="Acme Budget Camera",
        text="Check out the Acme Budget Camera review hub for more details.",
        tags=["acme"],
        metadata={"outbound_links": []},
    )

    safe = make_page(
        url="https://example.com/reviews/acme-budget-camera",
        title="Acme Budget Camera Review",
        text="Full review of the Acme Budget Camera.",
        tags=["acme"],
        metadata={"is_pillar": True, "status_code": 200},
    )

    noindex_page = make_page(
        url="https://example.com/reviews/draft",
        title="Draft Review",
        text="Draft content",
        tags=["acme"],
        metadata={"status_code": 200},
        noindex=True,
    )

    redirect = make_page(
        url="https://example.com/reviews/redirect",
        title="Redirect",
        text="",
        metadata={"is_redirect": True, "status_code": 302},
    )

    spanish = make_page(
        url="https://example.com/es/reviews/acme",
        title="Reseña de la cámara Acme",
        text="Esta reseña cubre la cámara Acme.",
        tags=["reseñas"],
        lang="es",
    )

    corpus = [safe, noindex_page, redirect, spanish]
    suggestions = suggest_links(source, corpus, engine_config)
    urls = {item.target_url for item in suggestions}
    assert safe.url in urls
    assert noindex_page.url not in urls
    assert redirect.url not in urls
    assert spanish.url not in urls
