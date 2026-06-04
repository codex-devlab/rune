from rune.models.source import Chunk, InjectionSource
from rune.models.report import AnalysisReport, DedupPair, TriggerResult
from pathlib import Path


def test_chunk_token_count():
    chunk = Chunk(text="hello world", start_line=1, end_line=1, token_count=2)
    assert chunk.token_count == 2


def test_injection_source_total_tokens():
    chunks = [
        Chunk(text="a", start_line=1, end_line=1, token_count=10),
        Chunk(text="b", start_line=2, end_line=2, token_count=5),
    ]
    source = InjectionSource(
        path=Path("rules/git.md"),
        source_type="rule",
        trigger=None,
        chunks=chunks,
    )
    assert source.token_count == 15


def test_dedup_pair_confidence():
    pair = DedupPair(
        source_a=Path("a.md"),
        source_b=Path("b.md"),
        similarity=0.95,
        confidence="HIGH",
    )
    assert pair.confidence == "HIGH"


def test_analysis_report_level():
    report = AnalysisReport(
        total_tokens=0,
        sources=[],
        dedup_pairs=[],
        trigger_results=[],
        level=0,
    )
    assert report.level == 0
