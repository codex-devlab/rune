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
