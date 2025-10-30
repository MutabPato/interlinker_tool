# Interlinker Engine v2

Interlinker engine v2 upgrades the internal-linking pipeline with deterministic ranking, safer guardrails, and richer anchor logic. The engine is organised into pure functions so it can run inside batch jobs, cron tasks, or API workers with the same behaviour.

## Pipeline Overview

| Stage | Purpose | Key Modules |
| ----- | ------- | ----------- |
| Candidate generation | Broad recall pass combining lexical, semantic, entity, and taxonomy overlap | `engine_v2/candidates.py` |
| Feature extraction | Normalises similarity, authority, freshness, and risk scores into `[0, 1]` features | `engine_v2/features.py` |
| Scoring and rerank | Applies the logistic scoring model with configurable weights and penalties | `engine_v2/rank.py` |
| Anchors | Extracts natural anchors, enforces diversity + bounds, and returns deterministic offsets | `engine_v2/anchors.py` |
| Guardrails + placement | Filters risky targets, flags thin content, and chooses placement/limits | `engine_v2/filters.py`, `engine_v2/placement.py` |
| Coordinator | Orchestrates the pipeline, enforces money-page priorities, and aggregates metrics | `engine_v2/index.py` |

### Candidate Generation

1. **Lexical BM25** (title + body) using corpus-level token statistics.
2. **Cosine semantic similarity** with sparse TF vectors as an embedding fallback.
3. **Entity overlap** using light-weight heuristics for product/brand names.
4. **Tag & taxonomy overlap** for quick topical filters.
5. **Business rules** drop self/canonical duplicates, parameterised URLs (`utm_*`, `replytocom`), redirect/status ≥ 300 pages, and login/cart duplicates.
6. **Language control** prefers same-language pages; cross-language targets need shared tags to survive candidate selection.
7. **Review bias** adds a multiplier to hub/product pages when the source is a review roundup.

### Feature Set

Each `(source, target)` pair generates features in `[0, 1]` (unless flagged as risk):

- `f_title_bm25`, `f_body_bm25`: BM25 scores normalised by configurable denominators.
- `f_semantic`: cosine similarity between TF embeddings.
- `f_entity_overlap`: weighted match (product > brand > category > generic).
- `f_tag_overlap`: Jaccard similarity of tag sets.
- `f_taxonomy_distance`: shared taxonomy depth fraction.
- `f_authority`: normalised authority (inlinks/PageRank proxy) or headless fallback.
- `f_click_depth`: 1 for shallow targets, decays with depth.
- `f_conversion_intent`: boost for review/category/product targets.
- `f_freshness`: recency half-life decay with a permissive minimum.
- `f_duplicate_risk`: 1 if the source already links to the target.
- `f_lang_match` / `f_lang_mismatch`: soft penalty for cross-language links.
- `f_quality`: blend of word-count normalisation and optional `content_score`/schema signals.

### Scoring Model

The transparent scoring function is logistic over a weighted linear combination of features:

```
score = σ(Σ w_i * f_i  −  Σ penalty_j * f_penalty_j)
```

All weights live in `engine_v2.yml`. Typical good links land in the `0.6 – 0.85` range. Penalties default to `f_duplicate_risk` and `f_lang_mismatch`, but the config allows extending/removing terms without code changes.

### Anchor Logic

- Extract phrases from target titles, head terms, overlapping entities, and brand names.
- Validate anchor length (2–7 words), avoid stop-word-only variants, and de-duplicate span overlaps.
- Score anchors by variant priority, contextual position, and length closeness to 4 words.
- Limit exact-match anchors to ≤ 40% of per-target selections.
- Ensure variant diversity by filling remaining slots with entity/brand/partial anchors when possible.
- Return stable character offsets relative to the cleaned source text.

### Placement & Limits

- Default link budget: `min(base_links_per_page + floor(words / 500), max_links_per_page)`.
- Hubs/pillars (metadata `is_pillar` or type `category`) default to `intro` placement; conversion targets default to `body`.
- Coordinator enforces at least one **sibling** and one **parent/hub** target when available, replacing the weakest suggestion if needed.
- Global guardrails forbid redirects, canonicalised pages, duplicates with tracking parameters, and mismatched languages with no shared tags.
- Risk flags include `lang_mismatch`, `thin_target`, and `dup_anchor` for downstream analysts.

### Metrics (Dry Run)

`engine_v2.index.dry_run` simulates a batch crawl and reports:

- Coverage rate, orphan rate, and simulated average click depth after linking.
- Anchor diversity (Shannon entropy) and per-variant counts.
- Duplicate-target rate per page (should be ~0 with guardrails).
- Mean scores for selected vs. rejected candidates.
- Language mismatch rate for suggested links.

## Configuration (`engine_v2.yml`)

Key tuning knobs:

- **Similarity norms**: `title_bm25_norm`, `body_bm25_norm` calibrate lexical feature magnitudes.
- **Budgets**: `max_candidates`, `base_links_per_page`, `max_links_per_page`, `max_anchors_per_target`.
- **Risk thresholds**: `product_wordcount_min`, `freshness_half_life_days`, `max_click_depth`.
- **Weights/Penalties**: `weights.{feature}` and `penalties.{feature}` map directly into the scoring formula.
- **Language policy**: `allow_cross_language` toggles hard blocks; otherwise, cross-language is permitted only with shared tags and receives penalties via `f_lang_mismatch`.

To tune, start with a validation set:

1. Lower `score_floor` while iterating—collect suggestions and label positives.
2. Increase weights for features that correlate with positive labels (e.g. `f_entity_overlap` for product-heavy sites).
3. Adjust penalties if duplicates slip through (raise `penalties.f_duplicate_risk`).
4. Rerun `bin/interlinker_v2 --dry-run` to observe metric deltas.

## Example Usage

```bash
bin/interlinker_v2 \
  --source fixtures/pages/sample_source.json \
  --corpus fixtures/pages/sample_corpus.json \
  --emit-json
```

Sample truncated output:

```json
[
  {
    "target_url": "https://example.com/reviews/acme-mega-camera",
    "reason": "strong shared entities; strong content overlap",
    "score": 0.78,
    "anchors": [
      {"text": "Acme Mega Camera Review Hub", "start": 68, "end": 95, "variant": "exact"},
      {"text": "Acme Mega Camera", "start": 12, "end": 28, "variant": "entity"}
    ],
    "placement_hint": "intro",
    "rel": "follow",
    "risk_flags": []
  }
]
```

## Blog vs. Review Examples

- **Blog how-to** posts usually surface category/pillar pages early (intro placement) and a complementary sibling how-to deeper in the body.
- **Review roundups** favour product detail pages with entity anchors and mark thin product content so editors can follow up.
- **Category hubs** generate child review/product links but throttle duplicates through the duplicate-risk penalty.

## Known Limitations & Roadmap

- Entity extraction relies on regex heuristics unless upstream services provide structured entities; integrating spaCy or a bespoke NER model would improve precision.
- Semantic similarity currently uses TF embeddings as a fallback; plugging in SentenceTransformers or Vertex AI embeddings is planned once dependency policy allows.
- Click-depth simulation is heuristic (subtracting 0.5 depth per new inbound). A full graph recompute would require the site-wide crawl graph.
- Anchor synonym expansion is limited to metadata head terms; integrating a synonyms lexicon would improve variety.
- Language detection assumes upstream fields are filled; future iterations may bundle fastText for on-the-fly detection.

## Future Work

- Online learning/Bandit updates based on click logs.
- Hard-negative mining to improve scoring calibration.
- Cached embeddings/BM25 indices stored per site for faster CLI dry runs.

For further integration notes, see module docstrings in `interlinker/engine_v2/`.
