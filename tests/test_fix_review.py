import builtins
import json

import pytest
from typer.testing import CliRunner

from rune.cli.main import app
from rune.review.types import ChunkRef
from rune.review.conflict_lexical import find_lexical_conflicts
from rune.review.conflict_nli import build_l2_candidates

runner = CliRunner()


def _ref(path: str, text: str, start: int = 1) -> ChunkRef:
    return ChunkRef(path=path, start_line=start, end_line=start, sha256="x", text=text)


# ---------------------------------------------------------------------------
# [높음-3] 모달 없는 흔한 충돌(use spaces vs use tabs) 탐지
# ---------------------------------------------------------------------------
def test_lexical_spaces_vs_tabs_detected():
    refs = [
        _ref("a.md", "Use spaces for indentation."),
        _ref("b.md", "Use tabs for indentation."),
    ]
    conflicts = find_lexical_conflicts(refs)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.source == "lexical"
    # 확신이 낮은 휴리스틱이므로 confidence 를 낮춰 표기
    assert c.confidence < 0.95


def test_lexical_modal_conflict_still_works():
    # 기존 always/never 탐지 회귀 없음
    refs = [
        _ref("a.md", "Always use spaces."),
        _ref("b.md", "Never use spaces."),
    ]
    conflicts = find_lexical_conflicts(refs)
    assert any(c.confidence == 0.95 for c in conflicts)


def test_lexical_no_false_positive_same_object():
    refs = [
        _ref("a.md", "Use spaces for indentation."),
        _ref("b.md", "Use spaces everywhere."),
    ]
    assert find_lexical_conflicts(refs) == []


def test_lexical_unrelated_objects_no_conflict():
    refs = [
        _ref("a.md", "Use spaces for indentation."),
        _ref("b.md", "Use docker for deployment."),
    ]
    assert find_lexical_conflicts(refs) == []


# ---------------------------------------------------------------------------
# [치명-2] L2 후보 생성 함수 (모델 다운로드 없이 검증)
# ---------------------------------------------------------------------------
def test_build_l2_candidates_by_topic_overlap():
    refs = [
        _ref("a.md", "Deploy to production on Friday afternoon."),
        _ref("b.md", "Never deploy to production on Friday."),
        _ref("c.md", "Write docstrings for every function."),
    ]
    pairs = build_l2_candidates(refs)
    pair_paths = {(p[0].path, p[1].path) for p in pairs}
    # a,b 는 토픽(deploy/production/friday)이 겹쳐 후보가 되어야 한다
    assert ("a.md", "b.md") in pair_paths
    # c 는 무관 → a/c, b/c 후보 아님
    assert ("a.md", "c.md") not in pair_paths
    assert ("b.md", "c.md") not in pair_paths


def test_build_l2_candidates_independent_of_l1():
    # L1 이 0건이어도 L2 후보는 생성될 수 있어야 한다(의미 레이어가 어휘 레이어 초월)
    refs = [
        _ref("a.md", "Production deploys require manual approval from a lead."),
        _ref("b.md", "Production deploys can ship automatically without approval."),
    ]
    assert find_lexical_conflicts(refs) == []  # L1 0건
    pairs = build_l2_candidates(refs)
    assert len(pairs) == 1  # L2 후보는 존재


def test_build_l2_candidates_shared_verb():
    refs = [
        _ref("a.md", "Run lint before merge."),
        _ref("b.md", "Run formatter after merge."),
    ]
    pairs = build_l2_candidates(refs)
    assert len(pairs) == 1


def test_build_l2_candidates_max_pairs_cap():
    refs = [_ref(f"f{i}.md", "deploy production release tag") for i in range(40)]
    pairs = build_l2_candidates(refs, max_pairs=5)
    assert len(pairs) == 5


# ---------------------------------------------------------------------------
# [높음-5] CLI 인자 순서: path 가 옵션 앞/뒤 어느 순서든 동일 JSON
# ---------------------------------------------------------------------------
def test_cli_arg_order_path_before_json(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nUse spaces.\n")
    r1 = runner.invoke(app, ["review", str(tmp_path), "--json"])
    r2 = runner.invoke(app, ["review", "--json", str(tmp_path)])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    assert json.loads(r1.output) == json.loads(r2.output)


def test_cli_arg_order_detects_conflict(tmp_path):
    # 충돌 지시문을 별도 규칙 파일로 분리(별도 청크가 되어 교차 비교 대상이 됨)
    (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "style_a.md").write_text(
        "## Style\n\nTrigger: format\n\nUse spaces for indentation."
    )
    (rules / "style_b.md").write_text(
        "## Style\n\nTrigger: format\n\nUse tabs for indentation."
    )
    r = runner.invoke(app, ["review", str(tmp_path), "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert len(data["conflicts"]) >= 1


# ---------------------------------------------------------------------------
# [치명-1] textual 미설치 시 TUI 대신 텍스트 리포트 + 정상 종료
# ---------------------------------------------------------------------------
def test_review_textual_missing_graceful(tmp_path, monkeypatch):
    import sys

    (tmp_path / "CLAUDE.md").write_text(
        "# P\n\nUse spaces for indentation.\nUse tabs for indentation.\n"
    )
    # 이미 import 된 tui 모듈을 제거하고, textual import 를 실패시킨다
    monkeypatch.delitem(sys.modules, "rune.review.tui", raising=False)
    monkeypatch.delitem(sys.modules, "textual", raising=False)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "textual" or name.startswith("textual."):
            raise ImportError("forced: textual not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # 기본 실행(--json 없음) → TUI 시도 → textual 없음 → 텍스트 리포트
    r = runner.invoke(app, ["review", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert "conflicts" in r.output or "충돌" in r.output
    assert "pip install textual" in r.output
