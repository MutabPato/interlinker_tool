"""Multilingual behaviour tests."""

from __future__ import annotations

from interlinker.engine_v2.index import suggest_links

from .conftest import make_page


def test_multilingual_prefers_same_language(engine_config):
    source = make_page(
        url="https://example.com/fr/blog/appareil-acme",
        title="Guide de l'appareil photo Acme",
        text="Ce guide couvre l'appareil photo Acme et renvoie au hub des meilleures offres.",
        lang="fr",
        tags=["acme", "photo"],
        metadata={"outbound_links": []},
    )

    fr_target = make_page(
        url="https://example.com/fr/reviews/acme",
        title="Test de l'appareil photo Acme",
        text="Test complet de l'appareil photo Acme.",
        lang="fr",
        tags=["acme", "photo"],
        type="review",
        metadata={"authority_score": 0.8},
    )

    en_hub = make_page(
        url="https://example.com/en/reviews/acme",
        title="Acme Camera Review Hub",
        text="Full Acme camera review hub with buying tips.",
        lang="en",
        tags=["acme", "photo"],
        type="review",
        metadata={"is_pillar": True, "authority_score": 0.9},
    )

    en_misc = make_page(
        url="https://example.com/en/blog/other",
        title="Other Camera Tips",
        text="General tips for other cameras.",
        lang="en",
        tags=["camera"],
    )

    corpus = [fr_target, en_hub, en_misc]
    suggestions = suggest_links(source, corpus, engine_config)

    assert suggestions, "Expected multilingual suggestions"
    assert suggestions[0].target_url == fr_target.url
    if len(suggestions) > 1:
        assert suggestions[1].target_url == en_hub.url
        assert "lang_mismatch" in suggestions[1].risk_flags
