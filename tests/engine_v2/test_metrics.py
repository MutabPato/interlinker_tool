"""Metrics aggregation tests."""

from __future__ import annotations

from interlinker.engine_v2.index import dry_run

from .conftest import make_page


def test_dry_run_returns_expected_metrics(engine_config):
    source = make_page(
        url="https://example.com/blog/source",
        title="Source Page",
        text="Linking to Acme Gadget Review Hub for more info.",
        tags=["acme"],
        metadata={"outbound_links": []},
    )

    target = make_page(
        url="https://example.com/reviews/acme-gadget",
        title="Acme Gadget Review Hub",
        text="Extensive Acme gadget review content.",
        tags=["acme"],
        metadata={"is_pillar": True, "authority_score": 0.8},
    )

    metrics = dry_run([source], [source, target], engine_config)

    expected_keys = {
        "coverage",
        "orphan_rate",
        "avg_click_depth_after",
        "anchor_diversity_index",
        "dup_target_rate",
        "mean_score_selected",
        "mean_score_rejected",
        "language_mismatch_rate",
        "anchor_variant_counts",
    }
    assert expected_keys.issubset(metrics.keys())
    assert 0.0 <= metrics["coverage"] <= 1.0
    assert isinstance(metrics["anchor_variant_counts"], dict)
