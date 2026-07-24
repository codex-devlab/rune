"""빈 'Trigger:' 줄이 다음 본문을 스코프로 오인 캡처하던 false-negative 회귀 방지.

라운드2 scope-awareness가 도입한 _TRIGGER_RE 버그: 콜론 뒤 \\s* 가 개행을 삼켜
빈 Trigger 줄에서 (.+) 가 다음 본문 줄을 trigger 키워드로 잡았고, 그 결과 두 청크가
서로 다른 (가짜) 스코프로 판정되어 유효한 저신뢰(0.6) 충돌이 억제되었다.

라운드3: 문단 분리(Trigger: 줄과 본문이 별도 청크)로 인한 스코프 오탐 수정.
Trigger 줄이 없는 청크는 같은 파일에서 선행 Trigger 를 상속한다.
"""
import textwrap
from pathlib import Path

import pytest

import rune.review.conflict_lexical as _lex_mod
from rune.review.conflict_lexical import (
    _trigger_scope,
    _different_scope,
    _resolve_scope,
    find_lexical_conflicts,
)
from rune.review.types import ChunkRef


@pytest.fixture(autouse=True)
def _clear_file_cache():
    """각 테스트 전후로 파일 라인 캐시를 초기화해 테스트 간 오염을 방지한다."""
    _lex_mod._file_lines_cache.clear()
    yield
    _lex_mod._file_lines_cache.clear()


def _ref(text: str, ln: int = 1, path: Path = Path("CLAUDE.md")) -> ChunkRef:
    return ChunkRef(path=path, start_line=ln, end_line=ln, sha256="x", text=text)


# ---------------------------------------------------------------------------
# 기존 회귀 케이스(_TRIGGER_RE 수평공백 버그)
# ---------------------------------------------------------------------------

def test_empty_trigger_line_yields_empty_scope():
    # 빈 'Trigger:' 줄 다음에 본문이 와도 스코프는 비어야 한다(본문을 캡처하면 버그).
    assert _trigger_scope("Trigger:\n\nUse spaces for indentation.") == frozenset()


def test_real_trigger_line_still_parsed():
    assert _trigger_scope("Trigger: python, django\n\nUse spaces.") == frozenset(
        {"python", "django"}
    )


def test_empty_trigger_chunks_not_treated_as_different_scope():
    # _different_scope 는 이제 ChunkRef 를 받는다(시그니처 변경).
    # 경로가 실존하지 않아도 청크 자체 텍스트로 스코프 판정이 이뤄진다.
    a = _ref("Trigger:\n\nUse spaces for indentation.", ln=1)
    b = _ref("Trigger:\n\nUse tabs for indentation.", ln=1)
    # 둘 다 스코프가 비었으므로 '다른 스코프'가 아니다 → 충돌 억제되면 안 됨.
    assert _different_scope(a, b) is False


def test_low_confidence_conflict_not_suppressed_with_empty_trigger():
    a = _ref("Trigger:\n\nUse spaces for indentation.", ln=1)
    b = _ref("Trigger:\n\nUse tabs for indentation.", ln=5)
    conflicts = find_lexical_conflicts([a, b])
    assert any(
        c.confidence == 0.6 and "spaces" in c.reason and "tabs" in c.reason
        for c in conflicts
    ), "빈 Trigger 줄 때문에 유효한 0.6 충돌이 억제되면 안 된다"


def test_genuine_different_scopes_still_suppressed():
    # 진짜로 서로 다른 Trigger 를 가진 청크는 여전히 저신뢰 충돌을 억제해야 한다.
    a = _ref("Trigger: frontend\n\nUse spaces for indentation.", ln=1)
    b = _ref("Trigger: backend\n\nUse tabs for indentation.", ln=5)
    conflicts = find_lexical_conflicts([a, b])
    assert not any(c.confidence == 0.6 for c in conflicts), (
        "명백히 다른 스코프(frontend vs backend)의 저신뢰 충돌은 억제되어야 한다"
    )


# ---------------------------------------------------------------------------
# 라운드3: 문단 분리 Trigger 상속 케이스
# ---------------------------------------------------------------------------

def test_paragraph_split_trigger_inherited_different_scope(tmp_path: Path):
    """Trigger 줄과 본문이 빈 줄로 분리돼 별도 청크가 된 경우.

    파일에서 선행 Trigger 를 상속해 스코프를 결정하므로,
    python 스코프와 golang 스코프 청크 간의 저신뢰 충돌은 억제되어야 한다.
    """
    # 실제 파일을 만들어 파일 기반 상속이 동작하게 한다.
    content = textwrap.dedent("""\
        Trigger: python

        Use spaces for indentation.

        Trigger: golang

        Use tabs for indentation.
    """)
    rule_file = tmp_path / "CLAUDE.md"
    rule_file.write_text(content)

    # 청크 분리 시뮬레이션:
    # - chunk_a: "Use spaces..." — 본문만(Trigger 없음), 선행 Trigger: python 상속 기대
    # - chunk_b: "Use tabs..."   — 본문만(Trigger 없음), 선행 Trigger: golang 상속 기대
    chunk_a = ChunkRef(path=rule_file, start_line=3, end_line=3, sha256="a",
                       text="Use spaces for indentation.")
    chunk_b = ChunkRef(path=rule_file, start_line=7, end_line=7, sha256="b",
                       text="Use tabs for indentation.")

    # _resolve_scope 가 선행 Trigger 를 올바르게 상속하는지 확인.
    assert _resolve_scope(chunk_a) == frozenset({"python"}), \
        "chunk_a 는 선행 'Trigger: python' 을 상속해야 한다"
    assert _resolve_scope(chunk_b) == frozenset({"golang"}), \
        "chunk_b 는 선행 'Trigger: golang' 을 상속해야 한다"

    # 서로 다른 스코프이므로 저신뢰 충돌은 억제되어야 한다.
    conflicts = find_lexical_conflicts([chunk_a, chunk_b])
    assert not any(c.confidence == 0.6 for c in conflicts), (
        "python vs golang 문단분리 청크 간의 저신뢰 충돌은 스코프 차이로 억제되어야 한다"
    )


def test_paragraph_split_trigger_same_scope_still_detected(tmp_path: Path):
    """같은 스코프 내 문단분리 청크는 저신뢰 충돌이 탐지되어야 한다."""
    content = textwrap.dedent("""\
        Trigger: python

        Use spaces for indentation.

        Use tabs for indentation.
    """)
    rule_file = tmp_path / "CLAUDE.md"
    rule_file.write_text(content)

    # 두 본문 청크 모두 선행 'Trigger: python' 을 상속 → 같은 스코프.
    chunk_a = ChunkRef(path=rule_file, start_line=3, end_line=3, sha256="a",
                       text="Use spaces for indentation.")
    chunk_b = ChunkRef(path=rule_file, start_line=5, end_line=5, sha256="b",
                       text="Use tabs for indentation.")

    conflicts = find_lexical_conflicts([chunk_a, chunk_b])
    assert any(c.confidence == 0.6 for c in conflicts), (
        "같은 스코프(python) 내 spaces vs tabs 충돌은 탐지되어야 한다"
    )


def test_empty_trigger_line_no_inheritance_suppression(tmp_path: Path):
    """빈 'Trigger:' 줄(키워드 없음)은 상속해도 빈 스코프 → 충돌 억제 금지."""
    content = textwrap.dedent("""\
        Trigger:

        Use spaces for indentation.

        Use tabs for indentation.
    """)
    rule_file = tmp_path / "CLAUDE.md"
    rule_file.write_text(content)

    chunk_a = ChunkRef(path=rule_file, start_line=3, end_line=3, sha256="a",
                       text="Use spaces for indentation.")
    chunk_b = ChunkRef(path=rule_file, start_line=5, end_line=5, sha256="b",
                       text="Use tabs for indentation.")

    # 빈 Trigger: 를 상속해도 스코프가 비므로 충돌은 억제되면 안 된다.
    conflicts = find_lexical_conflicts([chunk_a, chunk_b])
    assert any(c.confidence == 0.6 for c in conflicts), (
        "빈 Trigger: 상속 후에도 유효한 0.6 충돌이 억제되면 안 된다"
    )
