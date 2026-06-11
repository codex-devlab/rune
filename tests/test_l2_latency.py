import os
import time
import pytest
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.conflict_nli import find_nli_conflicts


@pytest.mark.skipif(
    os.environ.get("RUNE_RUN_NLI") != "1",
    reason="NLI tests require RUNE_RUN_NLI=1 (loads ~440MB model)",
)
def test_l2_latency_1000_pairs():
    refs = [ChunkRef(path=Path("x"), start_line=i, end_line=i, sha256="x",
                     text=f"Always do thing {i}.") for i in range(50)]
    pairs = [(refs[i], refs[j]) for i in range(50) for j in range(i+1, 50)][:1000]
    t0 = time.perf_counter()
    find_nli_conflicts(pairs, allow_download=True)
    elapsed = time.perf_counter() - t0
    assert elapsed <= 30, f"L2 took {elapsed:.1f}s"
