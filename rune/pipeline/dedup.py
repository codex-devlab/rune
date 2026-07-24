import os

os.environ.setdefault("TQDM_DISABLE", "1")

from dataclasses import dataclass
from pathlib import Path

from rune.models.source import InjectionSource, Chunk
from rune.models.report import DedupPair

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.75

# 청크(규칙) 단위 비교 시 너무 짧은 텍스트는 잡음이므로 제외한다.
_MIN_CHUNK_CHARS = 16


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
