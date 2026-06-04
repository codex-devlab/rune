from rune.models.source import InjectionSource
from rune.models.report import TriggerResult


def extract_triggers(sources: list[InjectionSource]) -> list[TriggerResult]:
    """Extract trigger keywords from each source. Never raises."""
    results: list[TriggerResult] = []
    for source in sources:
        if source.trigger:
            keywords = [k.strip() for k in source.trigger.split(",") if k.strip()]
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="parsed")
            )
        else:
            keywords = _tfidf_keywords(source)
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="tfidf")
            )
    return results


def _tfidf_keywords(source: InjectionSource, top_n: int = 5) -> list[str]:
    """Extract top-N TF-IDF keywords from source text."""
    text = " ".join(c.text for c in source.chunks)
    if not text.strip():
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
        matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = np.asarray(matrix.todense()).flatten()
        top_indices = scores.argsort()[::-1][:top_n]
        return [feature_names[i] for i in top_indices if scores[i] > 0]
    except Exception:
        # fallback: split and return most common words
        words = [w.lower().strip(".,!?#*") for w in text.split()]
        freq: dict[str, int] = {}
        for w in words:
            if len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:top_n]
