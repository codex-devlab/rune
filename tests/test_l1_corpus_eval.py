"""
Corpus-level L1 precision/recall harness.

Loads ALL 40 fixture files into one ref list (one ChunkRef per non-empty line, matching
the per-file test approach) and runs find_lexical_conflicts ONCE over the combined corpus.
Measures pair-level P/R by tracking which source file each ref came from.

Classification:
  TP — both refs in the pair come from positive files
  FP — at least one ref comes from a negative file (cross-file noise)
  FN — a positive file contributed no ref that appeared in any fired pair

Cross-file positive↔positive pairs are also counted as TP: two positive files that
share the same verb+object with opposing modals are a legitimate conflict signal.
"""
import hashlib
import json
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.conflict_lexical import find_lexical_conflicts

FIXTURE = Path(__file__).parent / "fixtures" / "l1_conflicts"


def _load_all_line_refs() -> tuple[list[ChunkRef], dict[str, bool]]:
    """
    Returns (all_refs, file_label_map) where:
      - all_refs: one ChunkRef per non-empty line across all 40 fixture files
      - file_label_map: maps str(path) -> is_positive for each source file
    """
    labels = json.loads((FIXTURE / "labels.json").read_text())
    pos_set = set(labels["positives"])
    all_refs: list[ChunkRef] = []
    file_label_map: dict[str, bool] = {}

    for category, files in [("positives", labels["positives"]), ("negatives", labels["negatives"])]:
        for fname in files:
            p = FIXTURE / category / fname
            is_pos = fname in pos_set
            file_label_map[str(p)] = is_pos
            for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                sha = hashlib.sha256(line.encode()).hexdigest()
                all_refs.append(ChunkRef(
                    path=p, start_line=lineno, end_line=lineno,
                    sha256=sha, text=line,
                ))

    return all_refs, file_label_map


def test_l1_corpus_pr_baseline():
    """Establish corpus-level P/R baseline. Document the number; don't gate too tight."""
    refs, file_label_map = _load_all_line_refs()

    pairs = find_lexical_conflicts(refs)

    # Classify each fired pair at the file level
    tp = 0
    fp = 0
    for p in pairs:
        a_pos = file_label_map[str(p.a.path)]
        b_pos = file_label_map[str(p.b.path)]
        if a_pos and b_pos:
            # Both sides from positive files — genuine conflict (may be intra- or cross-file)
            tp += 1
        else:
            # At least one side from a negative file — false positive
            fp += 1

    # FN: positive files that contributed no ref appearing in any fired pair
    files_with_pairs: set[str] = set()
    for p in pairs:
        files_with_pairs.add(str(p.a.path))
        files_with_pairs.add(str(p.b.path))
    fn = sum(
        1 for path_str, is_pos in file_label_map.items()
        if is_pos and path_str not in files_with_pairs
    )

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)

    print(f"\nCorpus-level L1: TP={tp} FP={fp} FN={fn} P={precision:.2f} R={recall:.2f}")

    # Baseline thresholds — looser than per-file because cross-file noise is real.
    # The point is to establish a baseline, NOT to gate at the per-file 1.00/1.00 level.
    assert precision >= 0.50, f"corpus precision {precision:.2f} < 0.50 baseline"
    assert recall >= 0.30, f"corpus recall {recall:.2f} < 0.30 baseline"
