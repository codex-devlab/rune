import os
import pytest


@pytest.mark.skipif(
    os.environ.get("RUNE_RUN_NLI") != "1",
    reason="NLI tests require RUNE_RUN_NLI=1 (loads ~440MB model)",
)
def test_contradiction_idx_resolves_for_default_model():
    from rune.review.conflict_nli import DEFAULT_MODEL
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(DEFAULT_MODEL)
    id2label = model.config.id2label
    idx = next((i for i, lbl in id2label.items() if "contradict" in lbl.lower()), None)
    assert idx is not None, f"default model {DEFAULT_MODEL} missing contradiction label"


@pytest.mark.skipif(
    os.environ.get("RUNE_RUN_NLI") != "1",
    reason="NLI tests require RUNE_RUN_NLI=1",
)
def test_contradiction_idx_resolves_for_small_model():
    from rune.review.conflict_nli import SMALL_MODEL
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(SMALL_MODEL)
    id2label = model.config.id2label
    idx = next((i for i, lbl in id2label.items() if "contradict" in lbl.lower()), None)
    assert idx is not None, f"small model {SMALL_MODEL} missing contradiction label"
