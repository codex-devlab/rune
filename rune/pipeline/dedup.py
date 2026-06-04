import os

os.environ.setdefault("TQDM_DISABLE", "1")

from rune.models.source import InjectionSource
from rune.models.report import DedupPair

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.75


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
