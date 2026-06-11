from pathlib import Path
from rune.review.types import ChunkRef, ConflictPair

DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-base"
SMALL_MODEL = "cross-encoder/nli-distilroberta-base"


def _is_cached(model_name: str) -> bool:
    import os
    hf_home = os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
    cache_root = Path(hf_home) / "hub"
    if not cache_root.exists():
        return False
    expected = "models--" + model_name.replace("/", "--")
    return any(p.name == expected for p in cache_root.iterdir())


def find_nli_conflicts(
    candidate_pairs: list[tuple[ChunkRef, ChunkRef]],
    model_name: str = DEFAULT_MODEL,
    allow_download: bool = False,
) -> list[ConflictPair]:
    if not _is_cached(model_name) and not allow_download:
        raise SystemExit(
            f"L2 requires pre-cached model OR --allow-model-download.\n"
            f"Run: huggingface-cli download {model_name}\n"
        )
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(model_name)
    pairs: list[ConflictPair] = []
    for ref_a, ref_b in candidate_pairs:
        scores = model.predict([(ref_a.text, ref_b.text), (ref_b.text, ref_a.text)])
        # MNLI label order is typically [contradiction, entailment, neutral] for these models
        contradiction_score = max(scores[0][0], scores[1][0])
        if contradiction_score > 0.7:
            pairs.append(ConflictPair(
                a=ref_a, b=ref_b,
                reason=f"NLI contradiction score {contradiction_score:.2f}",
                confidence=float(contradiction_score),
                source="nli",
            ))
    return pairs
