"""Review-specific behaviour tests."""

from __future__ import annotations

from interlinker.engine_v2.index import suggest_links

from .conftest import make_page


def test_review_page_prioritises_products(engine_config):
    engine_config.raw["product_wordcount_min"] = 30
    engine_config.raw["max_links_per_page"] = 3

    source = make_page(
        url="https://example.com/reviews/best-coffee-makers",
        title="Best Coffee Makers 2024",
        text=(
            "Our Best Coffee Makers guide spotlights the AromaBrew Pro 500 and SteamPress Lite. "
            "Find out why these machines top the list."
        ),
        type="review",
        tags=["coffee", "appliances"],
        metadata={"outbound_links": []},
    )

    aromabrew_text = " ".join(["AromaBrew" for _ in range(40)])
    aromabrew = make_page(
        url="https://example.com/product/aromabrew-pro-500",
        title="AromaBrew Pro 500",
        text=f"AromaBrew Pro 500 coffee maker overview {aromabrew_text}.",
        type="product",
        tags=["coffee"],
        metadata={"authority_score": 0.7, "head_terms": ["AromaBrew Pro 500"]},
    )

    steampress = make_page(
        url="https://example.com/product/steampress-lite",
        title="SteamPress Lite",
        text="SteamPress Lite compact brewer for apartments.",
        type="product",
        tags=["coffee"],
        metadata={"authority_score": 0.5},
    )

    corpus = [aromabrew, steampress]
    suggestions = suggest_links(source, corpus, engine_config)

    target_urls = {suggestion.target_url for suggestion in suggestions}
    assert aromabrew.url in target_urls
    assert steampress.url in target_urls

    for suggestion in suggestions:
        anchor_texts = {anchor.text for anchor in suggestion.anchors}
        assert any(product_name in " ".join(anchor_texts) for product_name in ("AromaBrew", "SteamPress"))

    thin_flags = {
        suggestion.target_url: suggestion.risk_flags
        for suggestion in suggestions
    }
    assert "thin_target" not in thin_flags[aromabrew.url]
    assert "thin_target" in thin_flags[steampress.url]
