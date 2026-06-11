import json
import os
import pytest
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.conflict_nli import find_nli_conflicts, DEFAULT_MODEL, SMALL_MODEL

FIXTURE = Path(__file__).parent / "fixtures" / "nli_pairs" / "pairs.jsonl"


@pytest.mark.skipif(
    os.environ.get("RUNE_RUN_NLI") != "1",
    reason="NLI tests require RUNE_RUN_NLI=1 (loads ~440MB model)",
)
def test_l2_precision_recall():
    pairs_data = [json.loads(l) for l in FIXTURE.read_text().splitlines() if l.strip()]
    candidate_pairs = [
        (
            ChunkRef(path=Path("a"), start_line=1, end_line=1, sha256="x", text=p["a"]),
            ChunkRef(path=Path("b"), start_line=1, end_line=1, sha256="y", text=p["b"]),
        )
        for p in pairs_data
    ]
    detected = find_nli_conflicts(candidate_pairs, allow_download=True)
    detected_indices = set()
    for d in detected:
        for i, p in enumerate(pairs_data):
            if d.a.text == p["a"] and d.b.text == p["b"]:
                detected_indices.add(i)
    tp = sum(1 for i, p in enumerate(pairs_data) if p["label"] == "contradiction" and i in detected_indices)
    fp = sum(1 for i, p in enumerate(pairs_data) if p["label"] != "contradiction" and i in detected_indices)
    fn = sum(1 for i, p in enumerate(pairs_data) if p["label"] == "contradiction" and i not in detected_indices)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    print(f"NLI: TP={tp} FP={fp} FN={fn} P={precision:.2f} R={recall:.2f}")
    assert precision >= 0.85, f"P={precision:.2f}"
    assert recall >= 0.75, f"R={recall:.2f}"
