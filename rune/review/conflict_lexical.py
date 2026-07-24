import re
from pathlib import Path

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

# 상충 object 사전: 같은 슬롯에 대한 상반된 값.
# 보수적으로 잘 알려진 이항 대립쌍만 등록한다(과탐 방지).
# 각 항목은 정규화된(소문자) object 토큰 쌍.
OPPOSING_OBJECTS: list[frozenset[str]] = [
    frozenset({"spaces", "tabs"}),
    frozenset({"tab", "space"}),
    frozenset({"single", "double"}),
    frozenset({"camelcase", "snake_case"}),
    frozenset({"camelcase", "snakecase"}),
    frozenset({"https", "http"}),
    frozenset({"yarn", "npm"}),
    frozenset({"lf", "crlf"}),
]


def _opposing_objects(o1: str, o2: str) -> bool:
    if o1 == o2:
        return False
    pair = frozenset({o1, o2})
    return pair in OPPOSING_OBJECTS


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


def extract_verb_objects(text: str) -> list[tuple[str, str]]:
    """모달 유무와 무관하게 (verb, object) 쌍을 모두 추출한다.

    '같은 verb + 상충 object'(예: use spaces vs use tabs)처럼 모달 없이도
    드러나는 충돌을 잡기 위한 보조 추출기.
    """
    return [(m.group(1).lower(), m.group(2).lower()) for m in VERB_OBJ.finditer(text)]


# 콜론 앞뒤 공백은 수평 공백([^\S\n])만 허용한다. \s* 를 쓰면 개행까지 삼켜
# 빈 'Trigger:' 줄에서 (.+) 가 다음 본문 줄을 스코프로 오인 캡처한다(false-negative).
_TRIGGER_RE = re.compile(r"(?im)^[^\S\n]*trigger:[^\S\n]*(.+)$")


def _trigger_scope(text: str) -> frozenset[str]:
    """청크의 Trigger 키워드 집합(소문자)을 반환. 없으면 빈 집합."""
    m = _TRIGGER_RE.search(text)
    if not m:
        return frozenset()
    return frozenset(k.strip().lower() for k in m.group(1).split(",") if k.strip())


# 파일 경로 → 파일 전체 라인 목록 캐시(1 회 읽기).
# 스코프 상속 탐색 시 동일 파일을 반복 읽지 않도록 함수 범위 캐시를 사용한다.
_file_lines_cache: dict[str, list[str]] = {}


def _resolve_scope(ref: "ChunkRef") -> frozenset[str]:
    """청크의 스코프를 결정한다.

    우선순위:
    1. 청크 자체 텍스트에 Trigger 가 있으면 그것을 사용.
    2. 없으면(문단 분리로 Trigger 가 별도 청크가 된 경우) 같은 파일에서
       ref.start_line 이전에 등장하는 가장 가까운 Trigger: 줄을 상속한다.
    3. 파일 미존재 또는 읽기 실패 시 빈 집합(기존 보수성 유지).
    """
    # 1. 청크 자체에 Trigger 가 있으면 즉시 반환(추가 I/O 없음).
    scope = _trigger_scope(ref.text)
    if scope:
        return scope

    # 2. 선행 Trigger 상속 — 파일을 캐시에서 읽는다.
    # ChunkRef.path 는 Path 또는 str 일 수 있다(타 팀 테스트가 str 로 전달).
    # Path() 로 정규화해 .read_text() 호출이 안전하게 동작하도록 한다.
    path_key = str(ref.path)
    if path_key not in _file_lines_cache:
        try:
            _file_lines_cache[path_key] = Path(ref.path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            # 파일 미존재/읽기 실패: 빈 집합으로 fallback(기존 보수성 유지).
            _file_lines_cache[path_key] = []

    lines = _file_lines_cache[path_key]
    # start_line 은 1-based; 자기 청크 이전 줄(0-based: 0 ~ start_line-2)을 역순 탐색.
    search_end = min(ref.start_line - 1, len(lines))  # exclusive 상한(0-based)
    for idx in range(search_end - 1, -1, -1):
        m = _TRIGGER_RE.match(lines[idx])
        if m:
            kws = frozenset(k.strip().lower() for k in m.group(1).split(",") if k.strip())
            # 빈 'Trigger:' 줄은 키워드가 없으므로 빈 집합을 반환한다
            # (다음 줄 본문을 캡처하지 않음은 _TRIGGER_RE 가 이미 보장).
            return kws
    return frozenset()


def _different_scope(ref_a: "ChunkRef", ref_b: "ChunkRef") -> bool:
    """두 청크가 명백히 다른 스코프인지(서로 다른 Trigger, 교집합 없음) 판정.

    청크 내 Trigger 우선, 없으면 같은 파일의 선행 Trigger 를 상속해 스코프를 결정한다.
    한쪽이라도 스코프를 확정할 수 없으면(빈 집합) 보수적으로 '다르지 않다'로 판단해
    기존 탐지를 깨지 않는다. 모달 기반(0.95) 경로는 이 함수를 호출하지 않으므로 무영향.
    """
    sa, sb = _resolve_scope(ref_a), _resolve_scope(ref_b)
    if not sa or not sb:
        return False
    return sa.isdisjoint(sb)


def find_lexical_conflicts(refs: list[ChunkRef]) -> list[ConflictPair]:
    indexed: list[tuple[ChunkRef, list[tuple[str, str, str]], list[tuple[str, str]]]] = [
        (r, extract_triples(r.text), extract_verb_objects(r.text)) for r in refs
    ]
    pairs: list[ConflictPair] = []
    seen: set[tuple[int, int, str, str]] = set()  # (i, j, verb, object)
    seen_obj: set[tuple[int, int, str, str, str]] = set()  # (i, j, verb, o1, o2)
    for i in range(len(indexed)):
        ref_i, triples_i, vobj_i = indexed[i]
        for j in range(i + 1, len(indexed)):
            ref_j, triples_j, vobj_j = indexed[j]
            # 기존 규칙: 같은 verb+object 에 대한 상반 모달(always vs never 등)
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
            # 확장 규칙: 같은 verb + 상충 object (모달 불필요).
            # 보수적 사전(OPPOSING_OBJECTS)에 등록된 대립쌍만 인정하고,
            # 확신이 낮으므로 confidence 를 낮춰 표기한다.
            # 보수적 scope-awareness: 두 청크가 명백히 다른 스코프(서로 다른 Trigger,
            # 교집합 없음)면 저신뢰 휴리스틱 충돌은 오탐일 가능성이 높으므로 제외한다.
            # 모달 기반(always/never) 정탐 경로는 위에서 이미 처리되어 영향받지 않는다.
            scope_differs = _different_scope(ref_i, ref_j)
            for v1, o1 in vobj_i:
                for v2, o2 in vobj_j:
                    if v1 == v2 and _opposing_objects(o1, o2):
                        if scope_differs:
                            continue
                        lo, hi = sorted((o1, o2))
                        key = (i, j, v1, lo, hi)
                        if key in seen_obj:
                            continue
                        seen_obj.add(key)
                        pairs.append(ConflictPair(
                            a=ref_i, b=ref_j,
                            reason=f"conflicting object on {v1}: {o1} vs {o2}",
                            confidence=0.6,
                            source="lexical",
                        ))
    return pairs
