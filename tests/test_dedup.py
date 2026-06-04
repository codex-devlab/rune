from pathlib import Path
from rune.models.source import Chunk, InjectionSource
from rune.pipeline.dedup import find_dedup_pairs
from rune.models.report import DedupPair


def _make_source(path: str, text: str) -> InjectionSource:
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=None,
        chunks=[Chunk(text=text, start_line=1, end_line=1, token_count=len(text.split()))],
    )


def test_identical_sources_are_high_confidence():
    text = "Never force push main. Always run tests before deploy."
    s1 = _make_source("rules/git.md", text)
    s2 = _make_source("rules/duplicate.md", text)
    pairs = find_dedup_pairs([s1, s2])
    assert len(pairs) >= 1
    assert pairs[0].confidence == "HIGH"


def test_different_sources_produce_no_high_pairs():
    s1 = _make_source("rules/git.md", "Git rules: never force push main branch.")
    s2 = _make_source("rules/python.md", "Python rules: use type hints and write tests.")
    pairs = find_dedup_pairs([s1, s2])
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]
    assert len(high_pairs) == 0


def test_single_source_returns_empty():
    s = _make_source("rules/git.md", "Some content here.")
    pairs = find_dedup_pairs([s])
    assert pairs == []


def test_empty_list_returns_empty():
    assert find_dedup_pairs([]) == []


def test_confidence_thresholds():
    from rune.pipeline.dedup import _confidence
    assert _confidence(0.95) == "HIGH"
    assert _confidence(0.80) == "MEDIUM"
    assert _confidence(0.50) == "LOW"
