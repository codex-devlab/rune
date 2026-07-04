"""[데이터 손실 위험] --apply 자동 삭제의 per-finding confidence 게이트 검증.

라운드1에서 추가된 모달 없는 휴리스틱 충돌은 confidence=0.6(오탐 가능)이다.
--confirm-delete-heuristics 일괄 승인만으로 이 저신뢰 충돌의 c.b(유효 규칙)까지
자동 삭제되면 안 된다. 모달 기반 0.95 충돌은 기존대로 삭제되어야 한다.
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from rune.cli.main import app
from rune.review.types import ChunkRef
from rune.review.conflict_lexical import find_lexical_conflicts

runner = CliRunner()


def _ref(path: str, text: str, start: int = 1) -> ChunkRef:
    # conflict_lexical._resolve_scope 가 ref.path.read_text() 를 호출하므로
    # Path 객체로 변환한다. 파일이 없으면 read_text 실패 시 빈 스코프로 처리된다.
    return ChunkRef(path=Path(path), start_line=start, end_line=start, sha256="x", text=text)


def _write_rule(root, name: str, body: str):
    rules = root / ".claude" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    p = rules / name
    p.write_text(body)
    return p


# ---------------------------------------------------------------------------
# 저신뢰(0.6 휴리스틱) 충돌은 자동 삭제에서 제외 — 유효 규칙 보존
# ---------------------------------------------------------------------------
def test_low_confidence_conflict_not_auto_deleted(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
    a = _write_rule(tmp_path, "style_a.md", "Use spaces for indentation.\n")
    b = _write_rule(tmp_path, "style_b.md", "Use tabs for indentation.\n")
    before_a = a.read_text()
    before_b = b.read_text()

    r = runner.invoke(
        app,
        ["review", str(tmp_path), "--apply", "--yes", "--confirm-delete-heuristics"],
    )
    assert r.exit_code == 0, r.output
    # 두 유효 규칙 파일 모두 손대지 않아야 한다(저신뢰 제외)
    assert a.read_text() == before_a
    assert b.read_text() == before_b


def test_low_confidence_skip_message_emitted(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
    _write_rule(tmp_path, "style_a.md", "Use spaces for indentation.\n")
    _write_rule(tmp_path, "style_b.md", "Use tabs for indentation.\n")

    r = runner.invoke(
        app,
        ["review", str(tmp_path), "--apply", "--yes", "--confirm-delete-heuristics"],
    )
    assert r.exit_code == 0, r.output
    assert "자동 삭제에서 제외" in r.output


def test_low_confidence_apply_log_has_zero_conflict_ops(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
    _write_rule(tmp_path, "style_a.md", "Use spaces for indentation.\n")
    _write_rule(tmp_path, "style_b.md", "Use tabs for indentation.\n")

    r = runner.invoke(
        app,
        ["review", str(tmp_path), "--apply", "--yes",
         "--confirm-delete-heuristics", "--json"],
    )
    assert r.exit_code == 0, r.output
    # stderr 의 저신뢰 안내가 stdout JSON 뒤에 섞일 수 있으므로 선두 JSON 객체만 파싱.
    log, _ = json.JSONDecoder().raw_decode(r.output[r.output.index("{"):])
    # JSON / operation_log 계약 유지: ops 리스트 존재, 삭제 op 0건
    assert log["ops"] == []
    assert "timestamp" in log


# ---------------------------------------------------------------------------
# 모달 기반 0.95 충돌은 기존대로 자동 삭제(c.b 삭제)
# ---------------------------------------------------------------------------
def test_high_confidence_modal_conflict_still_deleted(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
    # 같은 청크 안에서 always/never 가 같이 잡히지 않도록 별도 파일로 분리.
    a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
    b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\n")

    # 사전 확인: 0.95 충돌이 실제로 탐지됨
    conflicts = find_lexical_conflicts([
        _ref(str(a), a.read_text()),
        _ref(str(b), b.read_text()),
    ])
    assert any(c.confidence == 0.95 for c in conflicts)

    r = runner.invoke(
        app,
        ["review", str(tmp_path), "--apply", "--yes",
         "--confirm-delete-heuristics", "--json"],
    )
    assert r.exit_code == 0, r.output
    log, _ = json.JSONDecoder().raw_decode(r.output[r.output.index("{"):])
    # c.b(두 번째 청크)가 삭제 대상이 되어 최소 1건 delete op 가 기록되어야 한다
    assert any(op["kind"] == "delete" for op in log["ops"])


# ---------------------------------------------------------------------------
# scope-awareness: 명백히 다른 Trigger 스코프면 저신뢰 충돌 자체를 제외
# ---------------------------------------------------------------------------
def test_scope_aware_disjoint_triggers_no_conflict():
    refs = [
        _ref("a.md", "Trigger: python\n\nUse spaces for indentation."),
        _ref("b.md", "Trigger: golang\n\nUse tabs for indentation."),
    ]
    # 서로 다른 스코프(python vs golang) → 저신뢰 휴리스틱 충돌 제외
    assert find_lexical_conflicts(refs) == []


def test_scope_aware_shared_trigger_still_conflict():
    refs = [
        _ref("a.md", "Trigger: format\n\nUse spaces for indentation."),
        _ref("b.md", "Trigger: format\n\nUse tabs for indentation."),
    ]
    # 같은 스코프(format) → 기존대로 충돌 탐지(회귀 없음)
    conflicts = find_lexical_conflicts(refs)
    assert len(conflicts) == 1
    assert conflicts[0].confidence == 0.6


def test_scope_aware_no_trigger_unaffected():
    # Trigger 가 없는(스코프 미상) 청크는 기존 동작 유지 — 충돌 탐지됨
    refs = [
        _ref("a.md", "Use spaces for indentation."),
        _ref("b.md", "Use tabs for indentation."),
    ]
    conflicts = find_lexical_conflicts(refs)
    assert len(conflicts) == 1


def test_scope_aware_modal_conflict_not_suppressed():
    # 다른 스코프라도 모달 기반(always/never) 정탐은 억제되면 안 된다
    refs = [
        _ref("a.md", "Trigger: python\n\nAlways use spaces."),
        _ref("b.md", "Trigger: golang\n\nNever use spaces."),
    ]
    conflicts = find_lexical_conflicts(refs)
    assert any(c.confidence == 0.95 for c in conflicts)
