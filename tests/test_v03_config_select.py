"""v0.3 config-select 그룹 검증.

(a) opposing.toml 병합으로 새 대립쌍 탐지.
(b) opposing.toml 형식 오류 시 내장 fallback.
(c) --select 로 특정 id 만 적용.
(d) unknown id → exit 2.
(e) --select + --from-report 조합.
(f) 0.6 충돌도 --select 명시 선택 시 적용(단일 규칙 청크).
"""
import hashlib
import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rune.cli.main import app
from rune.review.conflict_lexical import find_lexical_conflicts, _load_opposing_objects
from rune.review.types import ChunkRef, ConflictPair, DeadCandidate

runner = CliRunner()


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _ref(path: str, text: str, start: int = 1) -> ChunkRef:
    lines = text.splitlines()
    end = start + max(len(lines) - 1, 0)
    return ChunkRef(
        path=Path(path),
        start_line=start,
        end_line=end,
        sha256=_sha(text),
        text=text,
    )


def _write_rule(root: Path, name: str, body: str) -> Path:
    rules = root / ".claude" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    p = rules / name
    p.write_text(body)
    return p


def _invoke_apply(tmp_path: Path, *extra_args):
    return runner.invoke(
        app,
        ["review", str(tmp_path), "--apply", "--yes",
         "--confirm-delete-heuristics"] + list(extra_args),
    )


# ===========================================================================
# (a) opposing.toml 병합으로 새 대립쌍 탐지
# ===========================================================================

class TestOpposingTomlMerge:
    """프로젝트 .rune/opposing.toml 에 사용자 정의 대립쌍을 추가하면 탐지된다."""

    def test_custom_pair_detected(self, tmp_path):
        """opposing.toml 에 등록한 pair 가 find_lexical_conflicts 에서 탐지된다."""
        toml_dir = tmp_path / ".rune"
        toml_dir.mkdir()
        (toml_dir / "opposing.toml").write_text(
            'pairs = [["prettier", "eslint"]]\n'
        )
        r1 = _ref("a.md", "Use prettier for formatting.")
        r2 = _ref("b.md", "Use eslint for formatting.")
        conflicts = find_lexical_conflicts([r1, r2], repo_root=tmp_path)
        reasons = [c.reason for c in conflicts]
        assert any("prettier" in r and "eslint" in r for r in reasons), (
            f"expected prettier vs eslint conflict, got: {reasons}"
        )

    def test_custom_pair_not_detected_without_toml(self, tmp_path):
        """opposing.toml 없으면 커스텀 쌍은 내장 사전에 없으므로 탐지 안 됨."""
        r1 = _ref("a.md", "Use prettier for formatting.")
        r2 = _ref("b.md", "Use eslint for formatting.")
        conflicts = find_lexical_conflicts([r1, r2], repo_root=tmp_path)
        reasons = [c.reason for c in conflicts]
        assert not any("prettier" in r and "eslint" in r for r in reasons)

    def test_builtin_pairs_still_work_with_toml(self, tmp_path):
        """opposing.toml 이 있어도 내장 사전(spaces/tabs)은 계속 동작한다."""
        toml_dir = tmp_path / ".rune"
        toml_dir.mkdir()
        (toml_dir / "opposing.toml").write_text(
            'pairs = [["prettier", "eslint"]]\n'
        )
        r1 = _ref("a.md", "Use spaces for indentation.")
        r2 = _ref("b.md", "Use tabs for indentation.")
        conflicts = find_lexical_conflicts([r1, r2], repo_root=tmp_path)
        reasons = [c.reason for c in conflicts]
        assert any("spaces" in r and "tabs" in r for r in reasons)

    def test_repo_root_none_uses_builtin(self, tmp_path):
        """repo_root=None 이면 opposing.toml 을 탐색하지 않고 내장만 사용."""
        r1 = _ref("a.md", "Use spaces for indentation.")
        r2 = _ref("b.md", "Use tabs for indentation.")
        conflicts = find_lexical_conflicts([r1, r2], repo_root=None)
        assert len(conflicts) >= 1


# ===========================================================================
# (b) opposing.toml 형식 오류 시 내장 fallback
# ===========================================================================

class TestOpposingTomlFallback:
    """opposing.toml 이 깨져 있으면 내장 사전만 사용하고 예외를 전파하지 않는다."""

    def test_invalid_toml_syntax_fallback(self, tmp_path):
        """TOML 파싱 오류 → 내장 사전 그대로 반환, 예외 없음."""
        toml_dir = tmp_path / ".rune"
        toml_dir.mkdir()
        (toml_dir / "opposing.toml").write_text("pairs = [\n broken {\n")
        # 예외 없이 내장 목록이 반환돼야 한다.
        result = _load_opposing_objects(tmp_path)
        assert len(result) >= 1  # 내장 사전 항목 존재

    def test_invalid_pair_structure_fallback(self, tmp_path):
        """pairs 항목이 문자열 2개 배열이 아니면 내장 fallback."""
        toml_dir = tmp_path / ".rune"
        toml_dir.mkdir()
        # 쌍이 3개짜리 배열 → 형식 오류
        (toml_dir / "opposing.toml").write_text(
            'pairs = [["a", "b", "c"]]\n'
        )
        result = _load_opposing_objects(tmp_path)
        # fallback 시 내장 사전 그대로 반환.
        from rune.review.conflict_lexical import OPPOSING_OBJECTS
        assert set(map(frozenset, [])) | set(result) >= set(OPPOSING_OBJECTS)

    def test_pairs_not_list_fallback(self, tmp_path):
        """pairs 가 배열이 아니면 내장 fallback."""
        toml_dir = tmp_path / ".rune"
        toml_dir.mkdir()
        (toml_dir / "opposing.toml").write_text('pairs = "bad"\n')
        result = _load_opposing_objects(tmp_path)
        from rune.review.conflict_lexical import OPPOSING_OBJECTS
        for builtin in OPPOSING_OBJECTS:
            assert builtin in result

    def test_missing_toml_returns_builtin(self, tmp_path):
        """opposing.toml 파일 자체가 없으면 내장 사전만 반환."""
        result = _load_opposing_objects(tmp_path)
        from rune.review.conflict_lexical import OPPOSING_OBJECTS
        for builtin in OPPOSING_OBJECTS:
            assert builtin in result


# ===========================================================================
# (c) --select 로 특정 id 만 적용
# ===========================================================================

class TestSelectApply:
    """--select id1,id2 가 지정된 finding 만 op 로 변환하고 나머지는 건드리지 않는다."""

    def test_select_applies_only_targeted_finding(self, tmp_path):
        """두 충돌 중 하나만 --select 로 지정하면 그것만 삭제된다."""
        # 규칙 A: always use spaces → a_rule.md
        # 규칙 B: never use spaces (충돌 loser) → b_rule.md
        # 규칙 C: always use lf → c_rule.md
        # 규칙 D: never use lf (충돌 loser) → d_rule.md
        a = _write_rule(tmp_path, "a_rule.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "b_rule.md", "Never use spaces.\n")
        c = _write_rule(tmp_path, "c_rule.md", "Always use lf.\n")
        d = _write_rule(tmp_path, "d_rule.md", "Never use lf.\n")

        # 라이브 스캔으로 id 확인
        result_json = runner.invoke(
            app, ["review", str(tmp_path), "--json"]
        )
        assert result_json.exit_code == 0, result_json.output
        data = json.loads(result_json.output)
        conflicts = data.get("conflicts", [])

        # b_rule.md 가 loser 인 충돌 id 만 선택
        target_ids = [
            c["id"] for c in conflicts
            if "b_rule.md" in c["b"]["path"]
        ]
        assert target_ids, f"b_rule.md loser 충돌이 없음: {conflicts}"
        select_arg = ",".join(target_ids)

        result = _invoke_apply(tmp_path, "--select", select_arg)
        assert result.exit_code == 0, result.output

        # b_rule.md 는 삭제됐거나 내용이 없어야 함.
        assert not b.exists() or b.read_text().strip() == ""
        # d_rule.md 는 건드리지 않아야 함.
        assert d.exists() and "Never use lf" in d.read_text()

    def test_select_produces_id_in_json(self, tmp_path):
        """--json 출력의 각 conflict 에 id 필드가 포함된다."""
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        _write_rule(tmp_path, "b.md", "Never use spaces.\n")
        result = runner.invoke(app, ["review", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for c in data.get("conflicts", []):
            assert "id" in c, f"id 필드 없음: {c}"
            assert c["id"].startswith("c-"), f"잘못된 prefix: {c['id']}"

    def test_dead_candidate_has_id_in_json(self, tmp_path):
        """--json 출력의 dead_candidates 에도 id 필드가 포함된다."""
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        result = runner.invoke(app, ["review", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for d in data.get("dead_candidates", []):
            assert "id" in d, f"dead id 필드 없음: {d}"
            assert d["id"].startswith("d-"), f"잘못된 prefix: {d['id']}"


# ===========================================================================
# (d) unknown id → exit 2
# ===========================================================================

class TestSelectUnknownId:
    """존재하지 않는 id 를 --select 에 넣으면 exit 2 + 'unknown id' stderr."""

    def test_unknown_id_exits_2(self, tmp_path):
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        result = _invoke_apply(tmp_path, "--select", "c-deadbeef")
        assert result.exit_code == 2

    def test_unknown_id_message(self, tmp_path):
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        result = _invoke_apply(tmp_path, "--select", "c-deadbeef")
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "unknown" in combined.lower(), f"stderr 에 'unknown' 없음: {combined!r}"

    def test_partial_unknown_exits_2(self, tmp_path):
        """알려진 id + unknown id 혼합이면 unknown 때문에 exit 2."""
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        _write_rule(tmp_path, "b.md", "Never use spaces.\n")

        result_json = runner.invoke(app, ["review", str(tmp_path), "--json"])
        data = json.loads(result_json.output)
        known_id = data["conflicts"][0]["id"]

        result = _invoke_apply(
            tmp_path, "--select", f"{known_id},c-ffffffff"
        )
        assert result.exit_code == 2


# ===========================================================================
# (e) --select + --from-report 조합
# ===========================================================================

class TestSelectFromReport:
    """--select + --from-report: 리포트에서 지정 id 만 ops 로 구성."""

    def test_select_from_report_applies_targeted_only(self, tmp_path):
        """리포트 저장 후 --select + --from-report 로 특정 충돌만 삭제."""
        a = _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "b.md", "Never use spaces.\n")
        c_rule = _write_rule(tmp_path, "c.md", "Always use lf.\n")
        d_rule = _write_rule(tmp_path, "d.md", "Never use lf.\n")

        # 리포트 저장
        report_path = tmp_path / "report.json"
        result_json = runner.invoke(app, ["review", str(tmp_path), "--json"])
        assert result_json.exit_code == 0
        report_path.write_text(result_json.output)

        data = json.loads(result_json.output)
        conflicts = data["conflicts"]
        # b.md 가 loser 인 충돌 id
        target = [c["id"] for c in conflicts if "b.md" in c["b"]["path"]]
        assert target, "b.md loser 충돌이 없음"

        result = _invoke_apply(
            tmp_path,
            "--from-report", str(report_path),
            "--select", target[0],
        )
        assert result.exit_code == 0, result.output

        # b.md 삭제, d.md 보존
        assert not b.exists() or b.read_text().strip() == ""
        assert d_rule.exists() and "Never use lf" in d_rule.read_text()

    def test_select_from_report_unknown_id_exits_2(self, tmp_path):
        """--from-report + --select unknown → exit 2."""
        _write_rule(tmp_path, "a.md", "Always use spaces.\n")
        report_path = tmp_path / "report.json"
        result_json = runner.invoke(app, ["review", str(tmp_path), "--json"])
        report_path.write_text(result_json.output)

        result = _invoke_apply(
            tmp_path,
            "--from-report", str(report_path),
            "--select", "c-00000000",
        )
        assert result.exit_code == 2


# ===========================================================================
# (f) 0.6 충돌도 --select 명시 선택 시 적용(단일 규칙 청크)
# ===========================================================================

class TestSelectLowConfidence:
    """confidence=0.6 충돌은 일반 --apply 에서 차단되지만 --select 명시 시 적용된다."""

    def test_low_conf_blocked_by_default_apply(self, tmp_path):
        """opposing.toml 기반 0.6 충돌은 --apply 단독으로는 삭제 안 됨."""
        # spaces/tabs 는 내장 사전에 있고 confidence=0.6
        a = _write_rule(tmp_path, "a.md", "Use spaces for indentation.\n")
        b = _write_rule(tmp_path, "b.md", "Use tabs for indentation.\n")

        result = _invoke_apply(tmp_path)
        # b.md 가 삭제되지 않아야 함(저신뢰 차단)
        assert b.exists() and "tabs" in b.read_text()

    def test_low_conf_applied_by_select(self, tmp_path):
        """0.6 충돌을 --select 로 명시 선택하면 단일 규칙 청크에 한해 삭제 적용."""
        a = _write_rule(tmp_path, "a.md", "Use spaces for indentation.\n")
        b = _write_rule(tmp_path, "b.md", "Use tabs for indentation.\n")

        result_json = runner.invoke(app, ["review", str(tmp_path), "--json"])
        assert result_json.exit_code == 0
        data = json.loads(result_json.output)
        conflicts = data["conflicts"]

        # b.md 가 loser 인 0.6 충돌 id
        low_conf = [
            c["id"] for c in conflicts
            if abs(c["confidence"] - 0.6) < 0.01 and "b.md" in c["b"]["path"]
        ]
        assert low_conf, f"0.6 충돌 없음: {conflicts}"

        result = _invoke_apply(tmp_path, "--select", low_conf[0])
        assert result.exit_code == 0, result.output

        # b.md 가 삭제됐어야 함.
        assert not b.exists() or b.read_text().strip() == ""
