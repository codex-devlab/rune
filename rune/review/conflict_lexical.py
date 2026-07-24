import re
import sys
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


_OPPOSING_TOML_MAX_BYTES = 64 * 1024  # 64KB 상한 — 초과 시 내장만 사용
_OPPOSING_TOML_MAX_PAIRS = 500        # pairs 수 상한 — 초과 시 내장만 사용


def _load_opposing_objects(repo_root: "Path | None") -> list[frozenset[str]]:
    """내장 OPPOSING_OBJECTS 에 프로젝트 .rune/opposing.toml 을 병합하여 반환.

    파일이 없거나 형식 오류가 있으면 내장 목록만 반환하고 예외를 전파하지 않는다.
    오류 발생 시 stderr 1줄 안내만 출력한다(조용한 fallback).

    파일 크기 64KB 또는 pairs 수 500 초과 시 내장 사전만 사용한다(DoS 방지).

    opposing.toml 형식:
        pairs = [["spaces", "tabs"], ["lf", "crlf"]]
    """
    result = list(OPPOSING_OBJECTS)  # 내장 기본값 복사
    if repo_root is None:
        return result
    toml_path = Path(repo_root) / ".rune" / "opposing.toml"
    if not toml_path.exists():
        return result
    try:
        # 파일 크기 상한 검사 — 초과 시 내장 사전만 사용.
        file_size = toml_path.stat().st_size
        if file_size > _OPPOSING_TOML_MAX_BYTES:
            print(
                f"[rune] opposing.toml 이 너무 큽니다({file_size} bytes > "
                f"{_OPPOSING_TOML_MAX_BYTES}), 내장 사전만 사용합니다.",
                file=sys.stderr,
            )
            return result

        # tomllib 은 Python 3.11+ 표준 라이브러리.
        # 3.10 이하에서는 tomli 패키지로 fallback.
        try:
            import tomllib  # type: ignore[import]
        except ImportError:
            import tomli as tomllib  # type: ignore[import]
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        pairs = data.get("pairs", [])
        if not isinstance(pairs, list):
            raise ValueError("pairs 는 배열이어야 합니다")

        # pairs 수 상한 검사 — 초과 시 내장 사전만 사용.
        if len(pairs) > _OPPOSING_TOML_MAX_PAIRS:
            print(
                f"[rune] opposing.toml 의 pairs 수가 너무 많습니다({len(pairs)} > "
                f"{_OPPOSING_TOML_MAX_PAIRS}), 내장 사전만 사용합니다.",
                file=sys.stderr,
            )
            return result

        for pair in pairs:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(s, str) for s in pair)
            ):
                raise ValueError(f"각 쌍은 문자열 2개 배열이어야 합니다: {pair!r}")
            fs = frozenset(s.lower() for s in pair)
            if fs not in result:
                result.append(fs)
    except Exception as exc:
        print(
            f"[rune] opposing.toml 로드 실패, 내장 사전만 사용합니다: {exc}",
            file=sys.stderr,
        )
    return result


def _opposing_objects(o1: str, o2: str, opposing: "list[frozenset[str]] | None" = None) -> bool:
    if o1 == o2:
        return False
    pair = frozenset({o1, o2})
    table = opposing if opposing is not None else OPPOSING_OBJECTS
    return pair in table


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


# 파일 경로 → 파일 전체 라인 목록 캐시(find_lexical_conflicts 호출 단위로 클리어).
# 테스트 간 상태 누출 방지: find_lexical_conflicts 진입 시 초기화한다.
# _resolve_scope 는 이 캐시를 직접 참조하며, 전역 변수로 유지하되
# 호출자(find_lexical_conflicts)가 수명을 관리한다.
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


def _b_lines_for_modal(ref_b: ChunkRef, m2: str, v2: str, o2: str) -> "tuple[int, int] | None":
    """loser(b) 청크 내에서 모달 트리플(m2, v2, o2) 매치가 발생한 라인을 반환.

    청크의 각 라인을 개별 검사하여 처음으로 매치가 발생한 라인(1-based absolute)을
    (line, line) 튜플로 반환한다. 매치 라인을 특정할 수 없으면 None.
    """
    if not ref_b.text:
        return None
    chunk_lines = ref_b.text.splitlines()
    for offset, line in enumerate(chunk_lines):
        line_triples = extract_triples(line)
        for lm, lv, lo in line_triples:
            if lm == m2 and lv == v2 and lo == o2:
                abs_line = ref_b.start_line + offset
                return (abs_line, abs_line)
    return None


def _b_lines_for_obj(ref_b: ChunkRef, v2: str, o2: str) -> "tuple[int, int] | None":
    """loser(b) 청크 내에서 (verb, object) 매치가 발생한 라인을 반환.

    청크의 각 라인을 개별 검사하여 처음으로 매치가 발생한 라인(1-based absolute)을
    (line, line) 튜플로 반환한다. 매치 라인을 특정할 수 없으면 None.
    """
    if not ref_b.text:
        return None
    chunk_lines = ref_b.text.splitlines()
    for offset, line in enumerate(chunk_lines):
        vobjs = extract_verb_objects(line)
        for lv, lo in vobjs:
            if lv == v2 and lo == o2:
                abs_line = ref_b.start_line + offset
                return (abs_line, abs_line)
    return None


def find_lexical_conflicts(
    refs: list[ChunkRef],
    repo_root: "Path | None" = None,
) -> list[ConflictPair]:
    """어휘 기반 충돌 쌍을 탐지하여 반환한다.

    repo_root 가 주어지면 <repo_root>/.rune/opposing.toml 을 병합 로드하여
    사용자 정의 대립쌍을 추가로 인식한다. None 이면 내장 사전만 사용(하위 호환).
    """
    # 테스트 간 상태 누출 방지: 호출 단위로 파일 라인 캐시를 초기화한다.
    # (전역 캐시 _file_lines_cache 의 수명을 find_lexical_conflicts 호출에 귀속)
    _file_lines_cache.clear()

    opposing = _load_opposing_objects(repo_root)

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
                        # loser(j=b) 청크 내 매치 라인 계산(라인 정밀 삭제용).
                        b_lines = _b_lines_for_modal(ref_j, m2, v2, o2)
                        pairs.append(ConflictPair(
                            a=ref_i, b=ref_j,
                            reason=f"{m1} vs {m2} on {v1} {o1}",
                            confidence=0.95,
                            source="lexical",
                            b_lines=b_lines,
                        ))
            # 확장 규칙: 같은 verb + 상충 object (모달 불필요).
            # 보수적 사전(opposing)에 등록된 대립쌍만 인정하고,
            # 확신이 낮으므로 confidence 를 낮춰 표기한다.
            # 보수적 scope-awareness: 두 청크가 명백히 다른 스코프(서로 다른 Trigger,
            # 교집합 없음)면 저신뢰 휴리스틱 충돌은 오탐일 가능성이 높으므로 제외한다.
            # 모달 기반(always/never) 정탐 경로는 위에서 이미 처리되어 영향받지 않는다.
            scope_differs = _different_scope(ref_i, ref_j)
            for v1, o1 in vobj_i:
                for v2, o2 in vobj_j:
                    if v1 == v2 and _opposing_objects(o1, o2, opposing):
                        if scope_differs:
                            continue
                        lo, hi = sorted((o1, o2))
                        key = (i, j, v1, lo, hi)
                        if key in seen_obj:
                            continue
                        seen_obj.add(key)
                        # loser(j=b) 청크 내 매치 라인 계산(라인 정밀 삭제용).
                        b_lines = _b_lines_for_obj(ref_j, v2, o2)
                        pairs.append(ConflictPair(
                            a=ref_i, b=ref_j,
                            reason=f"conflicting object on {v1}: {o1} vs {o2}",
                            confidence=0.6,
                            source="lexical",
                            b_lines=b_lines,
                        ))
    return pairs
