import os
import re
import string

os.environ.setdefault("TQDM_DISABLE", "1")

from dataclasses import dataclass
from pathlib import Path

from rune.models.source import InjectionSource, Chunk
from rune.models.report import DedupPair

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.75

# 청크(규칙) 단위 비교 시 너무 짧은 텍스트는 잡음이므로 제외한다.
_MIN_CHUNK_CHARS = 16

# 서브청크(규칙 라인) 단위 최소 문자 수 — 16자 미만은 잡음 제외
_MIN_SUBCHUNK_CHARS = 16

# 서브청크 비교 결과 쌍 수 상한
_MAX_RULE_PAIRS = 500


@dataclass
class RuleDedupPair:
    """서브청크(규칙 라인) 단위 중복 쌍. 파일 간 혼재 상황도 탐지한다."""

    source_a: Path
    line_a: int  # 원본 파일에서의 라인 번호 (1-based)
    source_b: Path
    line_b: int
    text: str    # 정규화 전 원본 텍스트 (짧은 쪽 기준)
    similarity: float
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"


@dataclass
class ChunkDedupPair:
    """청크(규칙) 단위 중복 쌍. 같은 파일/다른 파일 모두 대상."""

    source_a: Path
    source_b: Path
    chunk_a_index: int
    chunk_b_index: int
    text_a: str
    text_b: str
    similarity: float
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    token_count: int  # 중복 청크 1개 제거 시 절약되는 토큰(작은 쪽 기준)


def _confidence(similarity: float) -> str:
    if similarity >= _HIGH_THRESHOLD:
        return "HIGH"
    if similarity >= _MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _normalize_rule(text: str) -> str:
    """규칙 라인 정규화: 소문자 변환, 공백 축약, 앞뒤 구두점 제거."""
    t = text.lower()
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(string.punctuation + " ")
    return t



# 불릿 또는 숫자 목록 패턴 (모듈 레벨 상수 — 반복 컴파일 방지)
_BULLET_RE = re.compile(r"^(\s*[-*]|\s*\d+\.)\s+\S")
# Trigger 키워드 포함 라인 제외 패턴
_TRIGGER_RE_DEDUP = re.compile(r"\bTrigger\b", re.IGNORECASE)


def _extract_rule_lines(source: InjectionSource) -> list[tuple[int, str, str]]:
    """청크에서 규칙 라인(불릿 -, *, 숫자. 로 시작하는 라인)을 추출한다.

    헤더(# ...) 및 Trigger 키워드 포함 라인, 비어있는 라인은 제외한다.
    반환: [(원본파일_라인번호, 원본텍스트, 정규화텍스트), ...]
    """

    entries: list[tuple[int, str, str]] = []
    for chunk in source.chunks:
        # chunk.start_line 은 1-based
        chunk_lines = chunk.text.splitlines()
        for offset, raw_line in enumerate(chunk_lines):
            line_no = chunk.start_line + offset
            stripped = raw_line.strip()
            if not stripped:
                continue
            # 헤더 제외
            if stripped.startswith("#"):
                continue
            # Trigger 라인 제외
            if _TRIGGER_RE_DEDUP.search(stripped):
                continue
            # 불릿 또는 숫자 목록 라인만 포함
            if not _BULLET_RE.match(raw_line):
                continue
            normalized = _normalize_rule(stripped)
            if len(normalized) < _MIN_SUBCHUNK_CHARS:
                continue
            entries.append((line_no, stripped, normalized))
    return entries


def find_dedup_rule_pairs(sources: list[InjectionSource]) -> list[RuleDedupPair]:
    """서브청크(규칙 라인) 단위 중복 쌍을 탐지한다.

    각 파일의 청크를 불릿/숫자 목록 라인 단위로 분해한 뒤, 파일 간
    동일(정규화 일치) 또는 고유사(코사인 >= 0.92) 쌍을 찾는다.
    같은 파일의 라인 쌍은 비교하지 않는다(파일 간 중복에 집중).

    sentence-transformers 없으면 TF-IDF fallback(_tfidf_compare 재사용).
    절대 예외를 던지지 않는다.
    """
    if len(sources) < 2:
        return []

    # (source_index, line_no, 원본텍스트, 정규화텍스트) 목록
    entries: list[tuple[int, int, str, str]] = []
    for src_idx, source in enumerate(sources):
        for line_no, raw_text, norm_text in _extract_rule_lines(source):
            entries.append((src_idx, line_no, raw_text, norm_text))

    if len(entries) < 2:
        return []

    # 정규화 동일 쌍은 유사도 1.0 으로 즉시 처리(임베딩 불필요)
    pairs: list[RuleDedupPair] = []
    seen_exact: dict[str, list[tuple[int, int, str]]] = {}
    for src_idx, line_no, raw_text, norm_text in entries:
        seen_exact.setdefault(norm_text, []).append((src_idx, line_no, raw_text))

    used_pairs: set[tuple[int, int, int, int]] = set()

    for norm_text, occurrences in seen_exact.items():
        # 파일이 다른 쌍만 처리
        for i in range(len(occurrences)):
            for j in range(i + 1, len(occurrences)):
                sa_idx, la, ta = occurrences[i]
                sb_idx, lb, tb = occurrences[j]
                if sa_idx == sb_idx:
                    continue
                key = (sa_idx, la, sb_idx, lb)
                if key in used_pairs:
                    continue
                used_pairs.add(key)
                pairs.append(RuleDedupPair(
                    source_a=sources[sa_idx].path,
                    line_a=la,
                    source_b=sources[sb_idx].path,
                    line_b=lb,
                    text=ta,
                    similarity=1.0,
                    confidence="HIGH",
                ))
                if len(pairs) >= _MAX_RULE_PAIRS:
                    pairs.sort(key=lambda p: p.similarity, reverse=True)
                    return pairs

    # 임베딩/TF-IDF 로 고유사(exact 가 아닌) 쌍 추가 탐색
    # exact 가 아닌 항목들만 추려서 비교
    norm_texts = [norm for (_si, _ln, _rt, norm) in entries]
    try:
        sim_matrix = _embed_and_compare(norm_texts)
    except Exception:
        try:
            sim_matrix = _tfidf_compare(norm_texts)
        except Exception:
            sim_matrix = None

    if sim_matrix is not None:
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                sa_idx, la, ta, na = entries[i]
                sb_idx, lb, tb, nb = entries[j]
                if sa_idx == sb_idx:
                    continue
                key = (sa_idx, la, sb_idx, lb)
                if key in used_pairs:
                    continue
                sim = sim_matrix[i][j]
                if sim < _HIGH_THRESHOLD:
                    continue
                used_pairs.add(key)
                pairs.append(RuleDedupPair(
                    source_a=sources[sa_idx].path,
                    line_a=la,
                    source_b=sources[sb_idx].path,
                    line_b=lb,
                    text=ta,
                    similarity=round(sim, 4),
                    confidence=_confidence(sim),
                ))
                if len(pairs) >= _MAX_RULE_PAIRS:
                    break
            if len(pairs) >= _MAX_RULE_PAIRS:
                break

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs


def find_dedup_pairs(sources: list[InjectionSource]) -> list[DedupPair]:
    """Find semantically similar source pairs using cosine similarity.
    Falls back to TF-IDF if sentence-transformers not installed.
    Never raises.
    """
    if len(sources) < 2:
        return []

    texts = [" ".join(c.text for c in s.chunks) for s in sources]

    try:
        similarities = _embed_and_compare(texts)
    except Exception:
        similarities = _tfidf_compare(texts)

    pairs: list[DedupPair] = []
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            sim = similarities[i][j]
            pairs.append(
                DedupPair(
                    source_a=sources[i].path,
                    source_b=sources[j].path,
                    similarity=round(sim, 4),
                    confidence=_confidence(sim),
                )
            )

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs


def _embed_and_compare(texts: list[str]) -> list[list[float]]:
    import logging
    from sentence_transformers import SentenceTransformer
    import numpy as np

    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    sim_matrix = (embeddings @ embeddings.T).tolist()
    return sim_matrix


def _tfidf_compare(texts: list[str]) -> list[list[float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(matrix).tolist()
    return sim_matrix


def find_dedup_chunk_pairs(sources: list[InjectionSource]) -> list[ChunkDedupPair]:
    """청크(규칙) 단위 의미 중복 쌍을 탐지한다.

    파일 전체를 합쳐 비교하던 기존 방식과 달리, 각 파일의 청크(문단/규칙)를
    개별 단위로 펼쳐 청크 대 청크로 코사인 유사도를 계산한다. 같은 파일 내부의
    중복과 서로 다른 파일에 걸친 중복을 모두 잡는다.

    sentence-transformers 가 없으면 TF-IDF fallback 을 사용한다. 절대 예외를
    던지지 않는다.
    """
    # (source, chunk_index, chunk) 평탄화. 너무 짧은 청크는 잡음이라 제외.
    entries: list[tuple[InjectionSource, int, Chunk]] = []
    for s in sources:
        for idx, c in enumerate(s.chunks):
            if len(c.text.strip()) < _MIN_CHUNK_CHARS:
                continue
            entries.append((s, idx, c))

    if len(entries) < 2:
        return []

    texts = [c.text for (_s, _i, c) in entries]

    try:
        similarities = _embed_and_compare(texts)
    except Exception:
        similarities = _tfidf_compare(texts)

    pairs: list[ChunkDedupPair] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            sim = similarities[i][j]
            conf = _confidence(sim)
            if conf == "LOW":
                continue
            sa, ia, ca = entries[i]
            sb, ib, cb = entries[j]
            pairs.append(
                ChunkDedupPair(
                    source_a=sa.path,
                    source_b=sb.path,
                    chunk_a_index=ia,
                    chunk_b_index=ib,
                    text_a=ca.text,
                    text_b=cb.text,
                    similarity=round(sim, 4),
                    confidence=conf,
                    token_count=min(ca.token_count, cb.token_count),
                )
            )

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs
