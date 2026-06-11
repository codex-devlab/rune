import re

POSITIVE_MODALS = {"always", "must", "shall", "should"}
NEGATIVE_MODALS = {"never", "must_not", "shall_not", "should_not", "do_not"}

NEG_PATTERNS = [
    (re.compile(r"\bmust\s+not\b", re.I), "must_not"),
    (re.compile(r"\bshall\s+not\b", re.I), "shall_not"),
    (re.compile(r"\bshould\s+not\b", re.I), "should_not"),
    (re.compile(r"\bdo\s+not\b", re.I), "do_not"),
    (re.compile(r"\bdon't\b", re.I), "do_not"),
    (re.compile(r"\bnever\b", re.I), "never"),
]
POS_PATTERNS = [
    (re.compile(r"\balways\b", re.I), "always"),
    (re.compile(r"\bmust\b", re.I), "must"),
    (re.compile(r"\bshall\b", re.I), "shall"),
    (re.compile(r"\bshould\b", re.I), "should"),
]

VERB_OBJ = re.compile(r"\b(use|run|deploy|write|validate|prefer|avoid|enable|disable)\s+([\w\-]+)", re.I)


def extract_triples(text: str) -> list[tuple[str, str, str]]:
    """Return list of (modal, verb, object). Modal is canonical lowercase token."""
    triples: list[tuple[str, str, str]] = []
    modals: list[tuple[int, str]] = []
    for pat, name in NEG_PATTERNS:
        for m in pat.finditer(text):
            modals.append((m.start(), name))
    for pat, name in POS_PATTERNS:
        for m in pat.finditer(text):
            # skip if already matched as part of a NEG pattern (e.g., "must not" already caught)
            if any(abs(m.start() - ns) < 10 and nn.endswith("_not") for ns, nn in modals):
                continue
            modals.append((m.start(), name))
    for m_pos, modal in modals:
        tail = text[m_pos:]
        vm = VERB_OBJ.search(tail)
        if vm:
            triples.append((modal, vm.group(1).lower(), vm.group(2).lower()))
    return triples


from rune.review.types import ChunkRef, ConflictPair


def _is_opposing(m1: str, m2: str) -> bool:
    return (m1 in POSITIVE_MODALS and m2 in NEGATIVE_MODALS) or \
           (m2 in POSITIVE_MODALS and m1 in NEGATIVE_MODALS)


def find_lexical_conflicts(refs: list[ChunkRef]) -> list[ConflictPair]:
    indexed: list[tuple[ChunkRef, list[tuple[str, str, str]]]] = [
        (r, extract_triples(r.text)) for r in refs
    ]
    pairs: list[ConflictPair] = []
    seen: set[tuple[int, int, str, str]] = set()  # (i, j, verb, object)
    for i in range(len(indexed)):
        ref_i, triples_i = indexed[i]
        for j in range(i + 1, len(indexed)):
            ref_j, triples_j = indexed[j]
            for m1, v1, o1 in triples_i:
                for m2, v2, o2 in triples_j:
                    if v1 == v2 and o1 == o2 and _is_opposing(m1, m2):
                        key = (i, j, v1, o1)
                        if key in seen:
                            continue
                        seen.add(key)
                        pairs.append(ConflictPair(
                            a=ref_i, b=ref_j,
                            reason=f"{m1} vs {m2} on {v1} {o1}",
                            confidence=0.95,
                            source="lexical",
                        ))
    return pairs
