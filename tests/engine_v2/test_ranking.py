"""Ranking and relevance tests for engine v2."""

from __future__ import annotations

from interlinker.engine_v2.index import suggest_links

from .conftest import make_page


def test_relevance_ranking(engine_config):
    source = make_page(
        url="https://example.com/blog/acme-mega-camera-tips",
        title="10 Tips for the Acme Mega Camera",
        text=(
            "The Acme Mega Camera is our go-to mirrorless body. "
            "This guide covers accessories and the Acme Mega Camera Review Hub "
            "for deeper dives into specs and bundles."
        ),
        tags=["camera", "acme"],
        metadata={"outbound_links": []},
    )

    hub = make_page(
        url="https://example.com/reviews/acme-mega-camera",
        title="Acme Mega Camera Review Hub",
        text="Comprehensive review of the Acme Mega Camera with accessories and buying advice.",
        tags=["camera", "acme"],
        type="review",
        metadata={
            "is_pillar": True,
            "click_depth": 2,
            "authority_score": 0.9,
            "head_terms": ["Acme Mega Camera review"],
            "taxonomy": ["electronics", "camera"],
        },
    )

    product = make_page(
        url="https://example.com/product/acme-mega-camera-body",
        title="Acme Mega Camera Body",
        text="Buy the Acme Mega Camera body with free shipping.",
        tags=["camera", "acme"],
        type="product",
        metadata={
            "click_depth": 3,
            "authority_score": 0.6,
            "head_terms": ["Acme Mega Camera"],
            "taxonomy": ["electronics", "camera"],
        },
    )

    tangent = make_page(
        url="https://example.com/blog/travel-bag",
        title="Travel Bag Packing Tips",
        text="Pack smarter with this travel bag checklist.",
        tags=["travel"],
        metadata={"click_depth": 4},
    )

    corpus = [hub, product, tangent]
    suggestions = suggest_links(source, corpus, engine_config)

    assert suggestions, "Expected at least one suggestion"
    assert suggestions[0].target_url == hub.url
    ordered_targets = [item.target_url for item in suggestions]
    assert product.url in ordered_targets
    assert ordered_targets.index(hub.url) < ordered_targets.index(product.url)
    assert tangent.url not in ordered_targets
