from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.conflict_lexical import find_lexical_conflicts

def _ref(text: str, path="x.md", sl=1, el=1) -> ChunkRef:
    return ChunkRef(path=Path(path), start_line=sl, end_line=el, sha256="x", text=text)

def test_finds_polarity_conflict():
    refs = [_ref("Always use TypeScript."), _ref("Never use TypeScript.", path="y.md")]
    pairs = find_lexical_conflicts(refs)
    assert len(pairs) == 1
    assert pairs[0].source == "lexical"

def test_no_false_positive_on_unrelated():
    refs = [_ref("Always use TypeScript."), _ref("Run tests fast.", path="y.md")]
    pairs = find_lexical_conflicts(refs)
    assert pairs == []

def test_no_duplicate_pairs_on_repeated_triples():
    """I3: same (verb, object) triple appearing multiple times in same chunk should not emit duplicate pairs"""
    refs = [
        _ref("Always use TypeScript. Always use TypeScript."),
        _ref("Never use TypeScript.", path="y.md"),
    ]
    pairs = find_lexical_conflicts(refs)
    assert len(pairs) == 1, f"expected 1 pair, got {len(pairs)}: {pairs}"
