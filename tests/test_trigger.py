from pathlib import Path
from rune.models.source import Chunk, InjectionSource
from rune.pipeline.trigger import extract_triggers
from rune.models.report import TriggerResult


def _make_source(path: str, text: str, trigger: str | None = None) -> InjectionSource:
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=trigger,
        chunks=[Chunk(text=text, start_line=1, end_line=len(text.splitlines()), token_count=10)],
    )


def test_extracts_explicit_trigger():
    source = _make_source(
        "rules/git.md",
        "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push.",
        trigger="git, commit, push",
    )
    results = extract_triggers([source])
    assert len(results) == 1
    assert "git" in results[0].keywords
    assert results[0].method == "parsed"


def test_falls_back_to_tfidf_when_no_trigger():
    source = _make_source(
        "rules/python.md",
        "Always use type hints. Write pytest tests. Use dataclasses over dicts.",
    )
    results = extract_triggers([source])
    assert len(results) == 1
    assert len(results[0].keywords) > 0
    assert results[0].method == "tfidf"


def test_empty_sources():
    assert extract_triggers([]) == []


def test_trigger_keywords_are_strings():
    source = _make_source(
        "rules/docs.md",
        "Trigger: readme, documentation\n\nKeep docs updated.",
        trigger="readme, documentation",
    )
    results = extract_triggers([source])
    assert all(isinstance(k, str) for k in results[0].keywords)
