import re
from rune.models.source import Chunk

_TRIGGER_PATTERN = re.compile(r"^(trigger|트리거)\s*:", re.IGNORECASE)
_BOLD_PATTERN = re.compile(r"\*\*.+?\*\*")


def score_chunks_structural(chunks: list[Chunk]) -> None:
    """Tier 1: score in-place based on structural signals."""
    for chunk in chunks:
        score = 0.0
        text = chunk.text

        # Header level (# = 3pts, ## = 2pts, ### = 1pt)
        if text.startswith("# "):
            score += 3.0
        elif text.startswith("## "):
            score += 2.0
        elif text.startswith("### "):
            score += 1.0

        # Trigger marker
        if _TRIGGER_PATTERN.search(text):
            score += 2.0

        # Bold text presence
        score += len(_BOLD_PATTERN.findall(text)) * 0.5

        # List items (instruction density)
        list_items = sum(1 for line in text.splitlines() if line.strip().startswith(("- ", "* ", "1.")))
        score += list_items * 0.3

        chunk.importance_score = score


def score_chunks_tfidf(chunks: list[Chunk]) -> None:
    """Tier 2: score in-place using TF-IDF cross-chunk importance."""
    if not chunks:
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        texts = [c.text for c in chunks]
        vectorizer = TfidfVectorizer(max_features=500, stop_words=None)
        matrix = vectorizer.fit_transform(texts)
        # Mean TF-IDF score per chunk = proxy for information density
        scores = np.asarray(matrix.mean(axis=1)).flatten()
        for chunk, score in zip(chunks, scores):
            chunk.importance_score += float(score)
    except ImportError:
        pass  # graceful skip if scikit-learn not installed
