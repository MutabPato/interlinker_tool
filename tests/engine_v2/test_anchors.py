"""Anchor selection tests."""

from __future__ import annotations

from interlinker.engine_v2 import anchors

from .conftest import make_page


def test_anchor_diversity(engine_config):
    engine_config.raw["max_anchors_per_target"] = 3

    source = make_page(
        url="https://example.com/blog/acme-lens",
        title="Why the Acme Prime Lens Shines",
        text=(
            "Our Acme Prime Lens review references the Acme Prime Lens Review Hub "
            "and the Acme brand craftsmanship. This Acme Prime Lens is versatile."
        ),
        metadata={"outbound_links": []},
    )

    target = make_page(
        url="https://example.com/reviews/acme-prime-lens",
        title="Acme Prime Lens Review Hub",
        text="Complete Acme Prime Lens review and buying guide for the Acme brand.",
        metadata={"head_terms": ["Acme Prime Lens"], "brand": "Acme"},
    )

    extracted = anchors.extract_candidate_anchors(source, target, engine_config.raw)
    selected = anchors.select_anchors(source, target, extracted, engine_config.raw)

    assert selected, "Expected anchor candidates to be selected"
    lengths = [len(anchor.text.split()) for anchor in selected]
    assert all(2 <= length <= 7 for length in lengths)
    variants = {anchor.variant for anchor in selected}
    assert len(variants) > 1, "Expected mix of anchor variants"
    exact_count = sum(1 for anchor in selected if anchor.variant == "exact")
    assert exact_count <= max(1, int(len(selected) * 0.4))
