import re

from rune.models.source import InjectionSource
from rune.models.report import TriggerResult

# 영어 전용 stopword 의존을 제거하고 한국어/영어 혼용 설정에 맞춘 최소 stopword 집합.
# sklearn의 "english"는 한국어를 전혀 거르지 못하므로 직접 둘 다 다룬다.
_STOPWORDS = {
    # 영어 고빈도 기능어
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "for", "of",
    "to", "in", "on", "at", "by", "is", "are", "be", "was", "were", "with",
    "as", "it", "this", "that", "these", "those", "from", "into", "over",
    "you", "your", "we", "our", "they", "their", "do", "does", "not", "no",
    "use", "using", "always", "never", "all", "any", "every", "before", "after",
    # 한국어 고빈도 조사/연결어/기능어
    "그리고", "그러나", "하지만", "또는", "또한", "이런", "저런", "그런",
    "이것", "그것", "저것", "있다", "없다", "한다", "하는", "하라", "한다면",
    "모든", "항상", "절대", "전에", "후에", "위해", "대해", "에서", "으로",
}

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[가-힣]{2,}")


def extract_triggers(sources: list[InjectionSource]) -> list[TriggerResult]:
    """Extract trigger keywords from each source. Never raises."""
    # IDF 모집단으로 쓸 전체 코퍼스(모든 source의 청크 텍스트)를 먼저 구성한다.
    corpus_texts = [_source_text(s) for s in sources]

    results: list[TriggerResult] = []
    for idx, source in enumerate(sources):
        if source.trigger:
            keywords = [k.strip() for k in source.trigger.split(",") if k.strip()]
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="parsed")
            )
        else:
            keywords = _tfidf_keywords(idx, corpus_texts)
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="tfidf")
            )
    return results


def _source_text(source: InjectionSource) -> str:
    return " ".join(c.text for c in source.chunks)


def _tfidf_keywords(target_idx: int, corpus_texts: list[str], top_n: int = 5) -> list[str]:
    """target_idx 문서의 상위 키워드를 추출한다.

    핵심 수정: 단일 문서에 TF-IDF를 적용하면 IDF가 모두 동일(상수)이라
    사실상 TF(빈도)만 남는다. 따라서
      - 코퍼스(전체 source)가 2개 이상이면 전체를 IDF 모집단으로 fit하고
        target 문서 행을 평가한다(IDF가 실제로 의미를 가짐).
      - 코퍼스가 단일 문서뿐이면 TF-IDF를 흉내내지 않고, 정직한
        빈도/길이정규화 기반 키워드 추출로 폴백한다.
    어떤 경우에도 예외를 던지지 않는다(기존 계약 유지).
    """
    text = corpus_texts[target_idx] if 0 <= target_idx < len(corpus_texts) else ""
    if not text.strip():
        return []

    # 의미 있는 문서(비어있지 않은) 개수를 센다.
    non_empty = sum(1 for t in corpus_texts if t.strip())

    if non_empty >= 2:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np

            vectorizer = TfidfVectorizer(
                max_features=100,
                stop_words=None,  # 영어 전용 stopword 제거; 토크나이저로 한/영 모두 처리
                token_pattern=_TOKEN_PATTERN.pattern,
                lowercase=True,
            )
            matrix = vectorizer.fit_transform(corpus_texts)
            feature_names = vectorizer.get_feature_names_out()
            row = np.asarray(matrix[target_idx].todense()).flatten()
            top_indices = row.argsort()[::-1][:top_n]
            keywords = [
                feature_names[i]
                for i in top_indices
                if row[i] > 0 and feature_names[i].lower() not in _STOPWORDS
            ]
            if keywords:
                return keywords
            # TF-IDF가 비면(전부 stopword 등) 빈도 폴백으로 내려간다.
        except Exception:
            pass

    # 단일 문서이거나 TF-IDF가 비정상일 때: 길이정규화 빈도 기반 추출.
    return _frequency_keywords(text, top_n)


def _frequency_keywords(text: str, top_n: int) -> list[str]:
    """길이정규화 빈도 기반 키워드 추출. stopword 제거 후 빈도순 상위 N개."""
    tokens = [m.group(0).lower() for m in _TOKEN_PATTERN.finditer(text)]
    freq: dict[str, int] = {}
    for tok in tokens:
        if tok in _STOPWORDS:
            continue
        freq[tok] = freq.get(tok, 0) + 1
    if not freq:
        return []
    # 빈도 내림차순, 동률은 사전순으로 안정 정렬.
    return sorted(freq, key=lambda w: (-freq[w], w))[:top_n]
