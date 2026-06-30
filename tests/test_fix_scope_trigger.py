"""빈 'Trigger:' 줄이 다음 본문을 스코프로 오인 캡처하던 false-negative 회귀 방지.

라운드2 scope-awareness가 도입한 _TRIGGER_RE 버그: 콜론 뒤 \\s* 가 개행을 삼켜
빈 Trigger 줄에서 (.+) 가 다음 본문 줄을 trigger 키워드로 잡았고, 그 결과 두 청크가
서로 다른 (가짜) 스코프로 판정되어 유효한 저신뢰(0.6) 충돌이 억제되었다.
"""
from pathlib import Path

from rune.review.conflict_lexical import (
    _trigger_scope,
    _different_scope,
    find_lexical_conflicts,
)
from rune.review.types import ChunkRef


def _ref(text: str, ln: int = 1) -> ChunkRef:
    return ChunkRef(path=Path("CLAUDE.md"), start_line=ln, end_line=ln, sha256="x", text=text)


def test_empty_trigger_line_yields_empty_scope():
    # 빈 'Trigger:' 줄 다음에 본문이 와도 스코프는 비어야 한다(본문을 캡처하면 버그).
    assert _trigger_scope("Trigger:\n\nUse spaces for indentation.") == frozenset()


def test_real_trigger_line_still_parsed():
    assert _trigger_scope("Trigger: python, django\n\nUse spaces.") == frozenset(
        {"python", "django"}
    )


def test_empty_trigger_chunks_not_treated_as_different_scope():
    a = "Trigger:\n\nUse spaces for indentation."
    b = "Trigger:\n\nUse tabs for indentation."
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
