from pathlib import Path
from rune.review.types import ChunkRef, ConflictPair, DeadCandidate, ReviewReport

def test_chunkref_carries_sha():
    ref = ChunkRef(path=Path("/x"), start_line=1, end_line=5, sha256="abc")
    assert ref.sha256 == "abc"

def test_report_serializes_json():
    report = ReviewReport(schema_version="1.0", conflicts=[], dead_candidates=[])
    d = report.to_dict()
    assert d["schema_version"] == "1.0"
