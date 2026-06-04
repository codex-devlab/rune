from rune.models.source import Chunk
from rune.pipeline.scorer import score_chunks_structural, score_chunks_tfidf


def test_structural_scores_header_higher():
    header_chunk = Chunk(text="## Important Rule", start_line=1, end_line=1, token_count=3)
    body_chunk = Chunk(text="Some regular text here.", start_line=3, end_line=3, token_count=5)
    score_chunks_structural([header_chunk, body_chunk])
    assert header_chunk.importance_score > body_chunk.importance_score


def test_structural_scores_trigger_marker():
    trigger_chunk = Chunk(text="Trigger: git, commit", start_line=1, end_line=1, token_count=4)
    plain_chunk = Chunk(text="Regular content.", start_line=3, end_line=3, token_count=2)
    score_chunks_structural([trigger_chunk, plain_chunk])
    assert trigger_chunk.importance_score > plain_chunk.importance_score


def test_structural_all_chunks_get_score():
    chunks = [
        Chunk(text=f"text {i}", start_line=i, end_line=i, token_count=2)
        for i in range(5)
    ]
    score_chunks_structural(chunks)
    assert all(c.importance_score >= 0 for c in chunks)


def test_tfidf_returns_scores(complex_project):
    from rune.pipeline.inventory import run_inventory
    sources, _ = run_inventory(complex_project)
    all_chunks = [c for s in sources for c in s.chunks]
    score_chunks_tfidf(all_chunks)
    assert any(c.importance_score > 0 for c in all_chunks)


def test_tfidf_empty_input():
    score_chunks_tfidf([])  # must not raise
