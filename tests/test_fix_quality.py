"""scorer/trigger 통계 품질 결함 수정 검증 테스트.

[품질-9] trigger._tfidf_keywords: 단일 문서 TF-IDF의 무의미한 IDF 문제 수정.
[품질-10] scorer.score_chunks_tfidf: 0 포함 평균으로 인한 길이 편향 수정.
"""

from pathlib import Path

from rune.models.source import Chunk, InjectionSource
from rune.pipeline.trigger import extract_triggers
from rune.pipeline.scorer import score_chunks_structural, score_chunks_tfidf


def _src(path: str, text: str, trigger: str | None = None) -> InjectionSource:
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=trigger,
        chunks=[Chunk(text=text, start_line=1, end_line=1, token_count=len(text.split()))],
    )


# ---------------------------------------------------------------------------
# [품질-9] trigger 키워드
# ---------------------------------------------------------------------------

def test_multi_source_keywords_are_discriminative():
    """다중 문서에서 IDF가 의미를 가져, 공통어가 아닌 변별력 있는 단어가 뽑힌다."""
    sources = [
        _src("a.md", "deploy production release rollback deploy deploy"),
        _src("b.md", "python pytest mypy typing python python"),
        _src("c.md", "database migration schema index database database"),
    ]
    results = extract_triggers(sources)
    assert all(r.method == "tfidf" for r in results)
    # 각 문서의 고유 핵심어가 자기 문서 키워드 상위에 나와야 한다.
    assert "deploy" in results[0].keywords
    assert "python" in results[1].keywords
    assert "database" in results[2].keywords


def test_single_document_falls_back_to_frequency():
    """단일 문서면 TF-IDF의 IDF가 무의미하므로 빈도 기반으로 직관적인 키워드가 나온다."""
    source = _src(
        "solo.md",
        "caching caching caching layer redis redis ttl",
    )
    results = extract_triggers([source])
    assert len(results) == 1
    assert results[0].method == "tfidf"  # 메서드 라벨 계약 유지
    kws = results[0].keywords
    assert len(kws) > 0
    # 가장 빈번한 단어가 맨 앞에 와야 한다.
    assert kws[0] == "caching"


def test_korean_keywords_supported():
    """영어 전용 stopword 의존 제거 — 한국어 문서에서도 키워드가 추출된다."""
    source = _src(
        "ko.md",
        "배포 배포 배포 롤백 카나리 카나리 모니터링",
    )
    results = extract_triggers([source])
    kws = results[0].keywords
    assert len(kws) > 0
    assert "배포" in kws
    # 조사/기능어성 stopword는 빠져야 한다(예: '모든', '항상' 같은 단어가 들어와도 제거).


def test_korean_stopwords_filtered():
    source = _src("ko2.md", "항상 항상 모든 모든 테스트 테스트 테스트 커버리지")
    results = extract_triggers([source])
    kws = results[0].keywords
    assert "항상" not in kws
    assert "모든" not in kws
    assert "테스트" in kws


def test_explicit_trigger_unchanged():
    """명시적 trigger는 그대로 파싱(기존 계약 회귀 없음)."""
    source = _src("g.md", "본문", trigger="git, commit, push")
    results = extract_triggers([source])
    assert results[0].method == "parsed"
    assert results[0].keywords == ["git", "commit", "push"]


def test_empty_text_returns_empty_keywords():
    """빈 본문이어도 예외 없이 빈 리스트."""
    source = _src("empty.md", "   ")
    results = extract_triggers([source])
    assert results[0].keywords == []


def test_extract_triggers_never_raises_on_empty_corpus():
    assert extract_triggers([]) == []


# ---------------------------------------------------------------------------
# [품질-10] scorer 정보 밀도
# ---------------------------------------------------------------------------

def test_density_not_diluted_by_length():
    """길이가 길다는 이유만으로 정보 밀도가 낮아지면 안 된다.

    동일한 변별 어휘를 반복하는 긴 청크와, 짧은 청크를 비교.
    기존 0-포함-평균 방식은 어휘가 많은 긴 청크를 부당하게 깎았다.
    수정 후(0 아닌 항 평균)는 길이에 휘둘리지 않아야 한다.
    """
    short = Chunk(text="alpha beta", start_line=1, end_line=1, token_count=2)
    long = Chunk(
        text=" ".join(["gamma delta epsilon zeta eta theta iota kappa"] * 5),
        start_line=2,
        end_line=2,
        token_count=40,
    )
    chunks = [short, long]
    score_chunks_tfidf(chunks)
    # 길이가 5배 긴 청크의 밀도가 짧은 청크의 절반 미만으로 폭락하지 않아야 한다.
    # (옛 mean(axis=1) 방식이라면 long이 short보다 훨씬 작아졌다.)
    assert long.importance_score > 0
    assert long.importance_score >= short.importance_score * 0.5


def test_density_is_additive_to_structural():
    """importance_score 누적 계약: structural 점수 위에 더해진다."""
    chunks = [
        Chunk(text="## Header rule alpha", start_line=1, end_line=1, token_count=4),
        Chunk(text="plain body text beta gamma", start_line=2, end_line=2, token_count=5),
    ]
    score_chunks_structural(chunks)
    before = [c.importance_score for c in chunks]
    score_chunks_tfidf(chunks)
    after = [c.importance_score for c in chunks]
    # tfidf 단계가 기존 structural 점수를 덮어쓰지 않고 더해야 한다.
    for b, a in zip(before, after):
        assert a >= b


def test_density_empty_input_no_raise():
    score_chunks_tfidf([])  # 예외 없어야 함


def test_density_all_chunks_nonneg():
    chunks = [
        Chunk(text=f"rule about topic {i} content here", start_line=i, end_line=i, token_count=6)
        for i in range(4)
    ]
    score_chunks_tfidf(chunks)
    assert all(c.importance_score >= 0 for c in chunks)


def test_density_single_chunk_no_raise():
    """청크가 하나뿐(코퍼스 단일)이어도 예외 없이 동작."""
    chunks = [Chunk(text="solo chunk content", start_line=1, end_line=1, token_count=3)]
    score_chunks_tfidf(chunks)
    assert chunks[0].importance_score >= 0
