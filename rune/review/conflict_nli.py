import re
from pathlib import Path
from rune.review.types import ChunkRef, ConflictPair

DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-base"
SMALL_MODEL = "cross-encoder/nli-distilroberta-base"

# 후보 사전필터에서 무시할 흔한 불용어(토큰 겹침 신호를 흐리는 단어).
_STOPWORDS = {
    "the", "a", "an", "to", "of", "for", "and", "or", "in", "on", "at",
    "is", "are", "be", "with", "that", "this", "it", "as", "by", "we",
    "you", "your", "our", "do", "not", "no", "all", "any", "use", "using",
}
# 지시문에서 자주 쓰이는 동사(같은 verb 휴리스틱용).
_DIRECTIVE_VERBS = {
    "use", "run", "deploy", "write", "validate", "prefer", "avoid",
    "enable", "disable", "commit", "push", "tag", "rotate", "add", "keep",
    "update", "squash", "force", "merge", "always", "never",
}

_TOKEN_RE = re.compile(r"[a-z0-9_][a-z0-9_\-]*")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def _verbs(tokens: set[str]) -> set[str]:
    return tokens & _DIRECTIVE_VERBS


def build_l2_candidates(
    refs: list[ChunkRef],
    min_overlap: int = 2,
    max_pairs: int = 500,
) -> list[tuple[ChunkRef, ChunkRef]]:
    """L2(NLI) 추론에 넘길 후보 청크 쌍을 생성한다.

    L1 결과에 의존하지 않고 '전체 청크 쌍'에 대한 경량 사전필터를 적용한다.
    어떤 쌍이 후보가 되려면 다음 중 하나를 만족해야 한다:
      - 불용어 제외 토큰 교집합이 min_overlap 이상(동일 토픽 휴리스틱), 또는
      - 동일한 지시 동사(같은 verb)를 공유.

    모델 다운로드/추론 없이 순수하게 동작하므로 단위 테스트가 가능하다.
    결과는 안정적 순서(입력 인덱스 순)이며 max_pairs 로 상한을 둔다.
    """
    indexed = [(r, _tokens(r.text)) for r in refs]
    pairs: list[tuple[ChunkRef, ChunkRef]] = []
    for i in range(len(indexed)):
        ref_i, tok_i = indexed[i]
        verbs_i = _verbs(tok_i)
        for j in range(i + 1, len(indexed)):
            ref_j, tok_j = indexed[j]
            overlap = tok_i & tok_j
            shared_verb = bool(verbs_i & _verbs(tok_j))
            if len(overlap) >= min_overlap or shared_verb:
                pairs.append((ref_i, ref_j))
                if len(pairs) >= max_pairs:
                    return pairs
    return pairs


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

    # Dynamically resolve contradiction label index — different cross-encoder checkpoints
    # have different label orderings; do not assume MNLI [contradiction, entailment, neutral]
    id2label = model.config.id2label
    contradiction_idx = next(
        (i for i, lbl in id2label.items() if "contradict" in lbl.lower()),
        None,
    )
    if contradiction_idx is None:
        raise RuntimeError(
            f"NLI model {model_name} has no 'contradiction' label in id2label={id2label}; "
            "incompatible checkpoint."
        )

    pairs: list[ConflictPair] = []
    for ref_a, ref_b in candidate_pairs:
        scores = model.predict([(ref_a.text, ref_b.text), (ref_b.text, ref_a.text)])
        contradiction_score = max(scores[0][contradiction_idx], scores[1][contradiction_idx])
        if contradiction_score > 0.7:
            pairs.append(ConflictPair(
                a=ref_a, b=ref_b,
                reason=f"NLI contradiction score {contradiction_score:.2f}",
                confidence=float(contradiction_score),
                source="nli",
            ))
    return pairs
