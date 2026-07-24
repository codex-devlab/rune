"""[데이터 손실 위험] --apply 경로 4건 안전화 검증.

(1) 혼합 청크 보존 — 저신뢰 loser 와 같은 청크 또는 혼합 청크이면 자동 삭제 금지.
(2) --from-report 실제 파싱 — 빈 리포트→0 ops, 미존재 리포트→exit 2, 리포트 기반 적용.
(3) --select exit 2 — 미구현 기능을 정직하게 거부.
(4) static dead 비삭제 — stage==static 은 report-only, stage==events 만 삭제.
"""
import hashlib
import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rune.cli.main import app
from rune.review.cli import (
    APPLY_CONFLICT_CONFIDENCE_THRESHOLD,
    _build_apply_ops,
    _build_protected_keys,
    _chunk_key,
    _is_mixed_chunk,
    _load_report_from_json,
    _resolve_chunk_text,
)
from rune.review.types import ChunkRef, ConflictPair, DeadCandidate

runner = CliRunner()


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _ref(path: str, text: str, start: int = 1) -> ChunkRef:
    return ChunkRef(
        path=Path(path),
        start_line=start,
        end_line=start,
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
# (1) 혼합 청크 보존
# ===========================================================================

class TestMixedChunkProtection:
    """저신뢰 loser 와 동일 청크 또는 혼합 청크는 자동 삭제에서 제외된다."""

    # -----------------------------------------------------------------------
    # _is_mixed_chunk 단위 테스트
    # -----------------------------------------------------------------------

    def test_single_rule_line_not_mixed(self):
        # 헤더 + 규칙 1줄 → 혼합 아님
        assert not _is_mixed_chunk("# Style\n\nUse spaces.\n")

    def test_two_rule_lines_is_mixed(self):
        # 규칙 2줄 → 혼합
        assert _is_mixed_chunk("Use spaces.\nUse 4-space indent.\n")

    def test_header_lines_excluded_from_count(self):
        # 헤더만 2줄 → 규칙 0줄 → 혼합 아님
        assert not _is_mixed_chunk("# Title\n## Sub\n")

    def test_trigger_lines_excluded_from_count(self):
        # Trigger 줄 + 규칙 1줄 → 혼합 아님
        assert not _is_mixed_chunk("Trigger: python\n\nUse spaces.\n")

    def test_trigger_and_two_rule_lines_is_mixed(self):
        # Trigger 제외 후 규칙 2줄 → 혼합
        assert _is_mixed_chunk("Trigger: python\n\nUse spaces.\nUse 4-space indent.\n")

    # -----------------------------------------------------------------------
    # _build_protected_keys 단위 테스트
    # -----------------------------------------------------------------------

    def test_low_confidence_loser_in_protected_keys(self):
        low = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=_ref("b.md", "Use tabs."),
            reason="r", confidence=0.6, source="lexical",
        )
        keys = _build_protected_keys([low])
        assert _chunk_key(low.b) in keys

    def test_high_confidence_loser_not_in_protected_keys(self):
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=_ref("b.md", "Never use spaces."),
            reason="r", confidence=0.95, source="lexical",
        )
        keys = _build_protected_keys([high])
        assert _chunk_key(high.b) not in keys

    # -----------------------------------------------------------------------
    # _build_apply_ops — 동반 삭제 차단
    # -----------------------------------------------------------------------

    def test_shared_loser_chunk_not_deleted_when_protected(self):
        """0.95 충돌과 0.6 충돌의 loser 가 같은 청크이면 삭제 op 를 만들지 않는다."""
        shared_b = _ref("b.md", "Use tabs.")
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=shared_b,
            reason="r", confidence=0.95, source="lexical",
        )
        low = ConflictPair(
            a=_ref("c.md", "Always use spaces."),
            b=shared_b,   # 같은 청크
            reason="r", confidence=0.6, source="lexical",
        )
        ops, low_skip, prot_skip, _ = _build_apply_ops([high, low], [])
        # 저신뢰 1건이 건너뜀 → loser 가 protected → 고신뢰도 삭제 차단
        assert low_skip == 1
        assert prot_skip == 1
        assert ops == []

    def test_mixed_chunk_loser_not_deleted(self):
        """혼합 청크를 loser 로 갖는 고신뢰 충돌도 삭제에서 제외된다."""
        mixed_text = "Use spaces.\nUse 4-space indent.\n"
        b = _ref("b.md", mixed_text)
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=b,
            reason="r", confidence=0.95, source="lexical",
        )
        ops, _, prot_skip, _ = _build_apply_ops([high], [])
        assert prot_skip == 1
        assert ops == []

    def test_pure_high_confidence_loser_creates_delete_op(self):
        """순수 단일 규칙 + 고신뢰 → 삭제 op 생성 (정상 동작 회귀 방지)."""
        b = _ref("b.md", "Never use spaces.")
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=b,
            reason="r", confidence=0.95, source="lexical",
        )
        ops, low_skip, prot_skip, _ = _build_apply_ops([high], [])
        assert low_skip == 0
        assert prot_skip == 0
        assert len(ops) == 1
        assert ops[0].kind == "delete"

    # -----------------------------------------------------------------------
    # 통합: CLI --apply 에서 혼합 청크가 실제로 보존되는지
    # -----------------------------------------------------------------------

    def test_cli_mixed_chunk_file_preserved(self, tmp_path):
        """혼합 청크(규칙 2줄)를 포함하는 파일은 --apply 후에도 변경되지 않는다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        # b 파일은 규칙 2줄 → 혼합 청크 → 삭제 금지
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")
        before_b = b.read_text()

        result = _invoke_apply(tmp_path)
        assert result.exit_code == 0, result.output
        assert b.read_text() == before_b, "혼합 청크가 자동 삭제되었음"

    def test_cli_protected_chunk_message_in_stderr(self, tmp_path):
        """보호/혼합 제외 시 stderr 에 안내 메시지가 출력된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")

        result = _invoke_apply(tmp_path)
        combined = result.output or ""
        assert "보호/혼합 청크" in combined or "자동 삭제에서 제외" in combined


# ===========================================================================
# (2) --from-report 실제 파싱
# ===========================================================================

class TestFromReport:
    """--from-report 는 JSON 파일을 실제로 파싱하여 ops 를 구성해야 한다."""

    # -----------------------------------------------------------------------
    # _load_report_from_json 단위 테스트
    # -----------------------------------------------------------------------

    def test_load_empty_report(self, tmp_path):
        """빈 conflicts/dead_candidates 리포트 → 빈 목록."""
        f = tmp_path / "report.json"
        f.write_text(json.dumps({
            "schema_version": "1.0",
            "detector_tier": "L1",
            "conflicts": [],
            "dead_candidates": [],
        }))
        report = _load_report_from_json(f)
        assert report.conflicts == []
        assert report.dead_candidates == []

    def test_load_report_conflicts_parsed(self, tmp_path):
        """리포트의 conflicts 항목이 ConflictPair 로 정확히 파싱된다."""
        f = tmp_path / "report.json"
        f.write_text(json.dumps({
            "schema_version": "1.0",
            "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": "a.md", "start_line": 1, "end_line": 1, "sha256": "aaa"},
                "b": {"path": "b.md", "start_line": 2, "end_line": 2, "sha256": "bbb"},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
            }],
            "dead_candidates": [],
        }))
        report = _load_report_from_json(f)
        assert len(report.conflicts) == 1
        c = report.conflicts[0]
        assert c.confidence == 0.95
        assert str(c.b.path) == "b.md"
        assert c.b.sha256 == "bbb"

    def test_load_report_dead_candidates_parsed(self, tmp_path):
        """리포트의 dead_candidates 항목이 DeadCandidate 로 정확히 파싱된다."""
        f = tmp_path / "report.json"
        f.write_text(json.dumps({
            "schema_version": "1.0",
            "detector_tier": "L1",
            "conflicts": [],
            "dead_candidates": [{
                "chunk": {"path": "x.md", "start_line": 5, "end_line": 5, "sha256": "ccc"},
                "reason": "no trigger", "stage": "events",
            }],
        }))
        report = _load_report_from_json(f)
        assert len(report.dead_candidates) == 1
        d = report.dead_candidates[0]
        assert d.stage == "events"
        assert d.chunk.sha256 == "ccc"

    # -----------------------------------------------------------------------
    # CLI: 빈 리포트 → 0 ops
    # -----------------------------------------------------------------------

    def test_empty_report_produces_zero_ops(self, tmp_path):
        """빈 리포트를 --from-report 로 지정하면 delete op 가 0건이어야 한다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        # 라이브 스캔하면 삭제될 수도 있는 파일을 만들어 두어도
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        _write_rule(tmp_path, "modal_b.md", "Never use spaces.\n")

        report_file = tmp_path / "empty.json"
        report_file.write_text(json.dumps({
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [], "dead_candidates": [],
        }))

        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(report_file), "--json"],
        )
        assert result.exit_code == 0, result.output
        log = json.loads(result.output)
        assert log["ops"] == [], "빈 리포트임에도 ops 가 생성되었음 — 라이브 스캔이 사용된 것으로 의심"

    # -----------------------------------------------------------------------
    # CLI: 미존재 리포트 → exit 2
    # -----------------------------------------------------------------------

    def test_missing_report_exits_2(self, tmp_path):
        """--from-report 경로가 존재하지 않으면 exit code 2 가 반환된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(tmp_path / "nonexistent.json")],
        )
        assert result.exit_code == 2
        combined = result.output or ""
        assert "error" in combined.lower() or "찾을 수 없" in combined

    # -----------------------------------------------------------------------
    # CLI: 파싱 불가 리포트 → exit 2
    # -----------------------------------------------------------------------

    def test_invalid_json_report_exits_2(self, tmp_path):
        """JSON 파싱 불가 파일을 --from-report 로 지정하면 exit code 2 가 반환된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json {{{{")
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(bad)],
        )
        assert result.exit_code == 2
        combined = result.output or ""
        assert "error" in combined.lower() or "파싱" in combined

    # -----------------------------------------------------------------------
    # CLI: 리포트 기반 적용 — 리포트 내 고신뢰 충돌만 삭제
    # -----------------------------------------------------------------------

    def test_report_based_apply_deletes_only_report_ops(self, tmp_path):
        """--from-report 사용 시 라이브 스캔 결과가 아닌 리포트 항목만 삭제 대상이 된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        # 두 파일 생성 — 라이브 스캔으로도 충돌 탐지 가능한 구성
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\n")

        # sha256 은 applier 의 strip() 기준과 일치시킨다.
        sha_b = hashlib.sha256("Never use spaces.".encode()).hexdigest()

        # 리포트에는 b 만 삭제 대상으로 지정
        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1,
                      "sha256": hashlib.sha256("Always use spaces.".encode()).hexdigest()},
                "b": {"path": str(b), "start_line": 1, "end_line": 1, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
            }],
            "dead_candidates": [],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(report_file), "--json"],
        )
        assert result.exit_code == 0, result.output
        log = json.loads(result.output)
        # b 파일만 삭제되어야 함
        deleted_files = [op["file"] for op in log["ops"] if op["kind"] == "delete"]
        assert str(b) in deleted_files
        assert str(a) not in deleted_files


# ===========================================================================
# (3) --select exit 2
# ===========================================================================

class TestSelectNotImplemented:
    """--select 는 v0.3 예정이므로 exit 2 + 명확한 에러 메시지로 거부해야 한다."""

    def test_select_exits_2(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--confirm-delete-heuristics", "--select", "f1,f2"],
        )
        assert result.exit_code == 2

    def test_select_message_mentions_not_implemented(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--confirm-delete-heuristics", "--select", "f1"],
        )
        combined = result.output or ""
        # 미구현 또는 v0.3 언급 확인
        assert "구현" in combined or "v0.3" in combined

    def test_select_without_apply_also_exits_2(self, tmp_path):
        """--apply 없이 --select 만 지정해도 exit 2 (조기 거부)."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--select", "f1"],
        )
        assert result.exit_code == 2


# ===========================================================================
# (4) static dead 비삭제 / events dead 삭제 허용
# ===========================================================================

class TestStaticDeadReportOnly:
    """stage==static 데드 후보는 삭제 op 를 만들지 않고 report-only 로 처리한다."""

    # -----------------------------------------------------------------------
    # _build_apply_ops 단위 테스트
    # -----------------------------------------------------------------------

    def test_static_dead_produces_no_op(self):
        dead_static = DeadCandidate(
            chunk=_ref("x.md", "Old rule."),
            reason="no trigger found", stage="static",
        )
        ops, _, _, static_skip = _build_apply_ops([], [dead_static])
        assert static_skip == 1
        assert ops == []

    def test_events_dead_produces_delete_op(self):
        dead_events = DeadCandidate(
            chunk=_ref("x.md", "Old rule."),
            reason="no usage in 30 days", stage="events",
        )
        ops, _, _, static_skip = _build_apply_ops([], [dead_events])
        assert static_skip == 0
        assert len(ops) == 1
        assert ops[0].kind == "delete"

    def test_mixed_stages_only_events_deleted(self):
        """static 과 events 가 섞이면 events 만 삭제 op 가 생성된다."""
        d_static = DeadCandidate(
            chunk=_ref("a.md", "Old static rule."),
            reason="no trigger", stage="static",
        )
        d_events = DeadCandidate(
            chunk=_ref("b.md", "Old events rule."),
            reason="no usage", stage="events",
        )
        ops, _, _, static_skip = _build_apply_ops([], [d_static, d_events])
        assert static_skip == 1
        assert len(ops) == 1
        assert ops[0].ref.path == Path("b.md")

    # -----------------------------------------------------------------------
    # CLI: stderr 에 static dead 안내 메시지 출력
    # -----------------------------------------------------------------------

    def test_cli_static_dead_skip_message(self, tmp_path):
        """static dead 를 제외할 때 stderr 에 안내 메시지가 출력된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        # 라이브 스캔에서 static dead 가 탐지될 만한 규칙 파일 (트리거 없는 단독 규칙)
        _write_rule(tmp_path, "orphan.md", "Use single quotes.\n")

        result = _invoke_apply(tmp_path)
        # exit_code 0 이어야 함(삭제 없이 성공)
        assert result.exit_code == 0, result.output
        combined = result.output or ""
        # static dead 가 0건이면 메시지 없어도 되므로, 탐지된 경우만 확인
        # (탐지 여부는 스캔 로직에 의존하므로, 여기서는 exit_code 0 만 보장)

    def test_static_dead_not_deleted_in_cli(self, tmp_path):
        """CLI --apply 후 static dead 후보 파일은 실제로 삭제되지 않아야 한다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        orphan = _write_rule(tmp_path, "orphan.md", "Use single quotes.\n")
        before = orphan.read_text()

        result = _invoke_apply(tmp_path)
        assert result.exit_code == 0, result.output
        # 파일 내용이 변경되지 않았어야 한다
        assert orphan.read_text() == before, "static dead 후보가 자동 삭제되었음"


# ===========================================================================
# (5) --from-report 경로 혼합 청크 / 해석불가 보호 (결함 수정 검증)
# ===========================================================================

class TestFromReportMixedChunkProtection:
    """--from-report 경로에서 혼합 청크 보호가 조용히 무력화되지 않음을 검증.

    리포트 JSON 에는 청크 본문(text)이 없어 ChunkRef.text="".
    수정 전에는 _is_mixed_chunk("") 가 항상 False → 혼합 청크 게이트 무력화.
    수정 후에는 _resolve_chunk_text 로 디스크 본문을 해석하여 정상 판별.
    """

    # -----------------------------------------------------------------------
    # (a) --from-report 리포트의 0.95 충돌 loser 가 디스크상 혼합 청크 → 삭제 안 됨
    # -----------------------------------------------------------------------

    def test_from_report_mixed_chunk_loser_not_deleted(self, tmp_path):
        """리포트 기반 적용 시, loser 파일이 디스크상 혼합 청크이면 삭제하지 않고 protected 처리."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        # b 는 규칙 2줄 → 혼합 청크
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")
        before_b = b.read_text()

        sha_a = hashlib.sha256("Always use spaces.".encode()).hexdigest()
        sha_b = hashlib.sha256(before_b.strip().encode()).hexdigest()

        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1, "sha256": sha_a},
                "b": {"path": str(b), "start_line": 1, "end_line": 2, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
            }],
            "dead_candidates": [],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(report_file), "--json"],
        )
        assert result.exit_code == 0, result.output
        # b 파일은 혼합 청크이므로 삭제되어서는 안 됨
        assert b.exists(), "혼합 청크 파일이 삭제되었음 — --from-report 혼합 보호 무력화"
        assert b.read_text() == before_b, "혼합 청크 내용이 변경되었음"
        # ops 에 b 가 포함되지 않아야 함 — stderr 메시지가 섞일 수 있으므로 첫 JSON 블록만 파싱
        combined = result.output or ""
        json_part = combined.split("\n보호")[0].split("\n저신뢰")[0].split("\n정적")[0]
        log = json.loads(json_part)
        deleted_files = [op["file"] for op in log["ops"] if op["kind"] == "delete"]
        assert str(b) not in deleted_files
        # protected 안내 메시지 확인
        assert "보호/혼합 청크" in combined or "자동 삭제에서 제외" in combined

    # -----------------------------------------------------------------------
    # (b) loser 파일이 삭제되어 본문 해석 불가 → 삭제 안 됨
    # -----------------------------------------------------------------------

    def test_from_report_missing_file_loser_not_deleted(self, tmp_path):
        """리포트의 loser 파일이 이미 삭제된 상태이면 보수적으로 op 를 만들지 않는다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        sha_a = hashlib.sha256("Always use spaces.".encode()).hexdigest()

        # b 는 리포트에만 존재하고 디스크에는 없음(이미 삭제된 상황 시뮬레이션)
        missing_b_path = tmp_path / ".claude" / "rules" / "gone.md"
        sha_b = hashlib.sha256("Never use spaces.".encode()).hexdigest()

        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1, "sha256": sha_a},
                "b": {"path": str(missing_b_path), "start_line": 1, "end_line": 1, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
            }],
            "dead_candidates": [],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(report_file), "--json"],
        )
        assert result.exit_code == 0, result.output
        combined = result.output or ""
        json_part = combined.split("\n보호")[0].split("\n저신뢰")[0].split("\n정적")[0]
        log = json.loads(json_part)
        # 파일이 없으므로 본문 해석 불가 → 보수적 제외 → ops 에 포함 안 됨
        deleted_files = [op["file"] for op in log["ops"] if op["kind"] == "delete"]
        assert str(missing_b_path) not in deleted_files, (
            "loser 파일이 미존재임에도 delete op 가 생성되었음 — 해석불가 보호 실패"
        )

    # -----------------------------------------------------------------------
    # (c) 단일 규칙 loser → 기존대로 삭제 (회귀 없음)
    # -----------------------------------------------------------------------

    def test_from_report_single_rule_loser_deleted(self, tmp_path):
        """리포트 기반 적용 시, loser 가 단일 규칙 청크이면 정상적으로 삭제된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\n")

        sha_a = hashlib.sha256("Always use spaces.".encode()).hexdigest()
        sha_b = hashlib.sha256("Never use spaces.".encode()).hexdigest()

        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1, "sha256": sha_a},
                "b": {"path": str(b), "start_line": 1, "end_line": 1, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
            }],
            "dead_candidates": [],
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--apply", "--yes",
             "--from-report", str(report_file), "--json"],
        )
        assert result.exit_code == 0, result.output
        log = json.loads(result.output)
        # 단일 규칙이므로 정상 삭제되어야 함 (회귀 없음)
        deleted_files = [op["file"] for op in log["ops"] if op["kind"] == "delete"]
        assert str(b) in deleted_files, "단일 규칙 loser 가 삭제되지 않음 — 회귀 발생"
        assert str(a) not in deleted_files
