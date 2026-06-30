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
        # 정보 밀도 프록시: '0이 아닌 항만의 평균' TF-IDF.
        # 기존 matrix.mean(axis=1)은 등장하지 않은 모든 항(0)까지 분모에 넣어,
        # 청크가 길거나 어휘가 다양할수록 평균이 부당하게 작아지는 결함이 있었다.
        # 실제로 등장한 항만 평균하면 길이/어휘 수에 휘둘리지 않고
        # "등장한 용어들의 평균 변별력"을 측정하므로 통계적으로 타당하다.
        dense = np.asarray(matrix.todense())
        nnz = np.count_nonzero(dense, axis=1)
        row_sum = dense.sum(axis=1)
        # 0으로 나누기 방지: 항이 하나도 없는 행은 밀도 0.
        scores = np.divide(
            row_sum,
            nnz,
            out=np.zeros_like(row_sum, dtype=float),
            where=nnz > 0,
        )
        # importance_score 누적 계약 유지: structural 점수에 더한다.
        for chunk, score in zip(chunks, scores):
            chunk.importance_score += float(score)
    except ImportError:
        pass  # graceful skip if scikit-learn not installed
