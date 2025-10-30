"""Link budget enforcement tests."""

from __future__ import annotations

from interlinker.engine_v2.index import suggest_links

from .conftest import make_page


def test_links_respect_budget_and_offsets(engine_config):
    engine_config.raw["max_links_per_page"] = 2
    engine_config.raw["base_links_per_page"] = 2
    engine_config.raw["score_floor"] = 0.3

    source_text = (
        "The Acme Prime Lens pairs well with the Acme Mega Camera Body. "
        "For accessories, see the Acme Lens Accessory Guide and the Acme Cleaning Kit."
    )
    source = make_page(
        url="https://example.com/blog/gear-roundup",
        title="Gear Roundup",
        text=source_text,
        metadata={"outbound_links": []},
    )

    targets = [
        make_page(
            url="https://example.com/product/acme-prime-lens",
            title="Acme Prime Lens",
            text="Acme Prime Lens specs and pricing.",
            type="product",
            metadata={"authority_score": 0.7, "head_terms": ["Acme Prime Lens"]},
        ),
        make_page(
            url="https://example.com/product/acme-mega-camera-body",
            title="Acme Mega Camera Body",
            text="Acme Mega Camera Body details.",
            type="product",
            metadata={"authority_score": 0.6, "head_terms": ["Acme Mega Camera"]},
        ),
        make_page(
            url="https://example.com/guides/acme-accessory",
            title="Acme Lens Accessory Guide",
            text="Guide to Acme lens accessories.",
            type="category",
            metadata={"is_pillar": True},
        ),
        make_page(
            url="https://example.com/cleaning-kit",
            title="Acme Cleaning Kit",
            text="Acme cleaning kit overview.",
            type="product",
            metadata={"authority_score": 0.5},
        ),
    ]

    suggestions = suggest_links(source, targets, engine_config)

    assert len(suggestions) <= 2
    assert len({item.target_url for item in suggestions}) == len(suggestions)

    for suggestion in suggestions:
        for anchor in suggestion.anchors:
            assert 0 <= anchor.start < anchor.end <= len(source_text)
