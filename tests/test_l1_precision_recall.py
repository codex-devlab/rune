import hashlib
import json
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.conflict_lexical import find_lexical_conflicts

FIXTURE = Path(__file__).parent / "fixtures" / "l1_conflicts"


def _refs_for_file(md_file: Path) -> list[ChunkRef]:
    """Return one ChunkRef per non-empty line in *md_file*."""
    refs: list[ChunkRef] = []
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        sha = hashlib.sha256(line.encode()).hexdigest()
        refs.append(ChunkRef(
            path=md_file,
            start_line=lineno,
            end_line=lineno,
            sha256=sha,
            text=line,
        ))
    return refs


def _has_conflict(md_file: Path) -> bool:
    """Return True iff the two rule-lines inside *md_file* form a lexical conflict."""
    refs = _refs_for_file(md_file)
    return len(find_lexical_conflicts(refs)) > 0


def test_l1_precision_recall_thresholds():
    labels = json.loads((FIXTURE / "labels.json").read_text())
    positives = labels["positives"]
    negatives = labels["negatives"]

    tp = sum(1 for p in positives if _has_conflict(FIXTURE / "positives" / p))
    fp_files = [n for n in negatives if _has_conflict(FIXTURE / "negatives" / n)]
    fp = len(fp_files)
    fn = len(positives) - tp

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)

    print(f"TP={tp} FP={fp} FN={fn} P={precision:.2f} R={recall:.2f}")
    print(f"FP files: {fp_files}")
    assert precision >= 0.90, f"precision {precision:.2f} < 0.90"
    assert recall >= 0.70, f"recall {recall:.2f} < 0.70"
