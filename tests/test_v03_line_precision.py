"""v0.3 라인 정밀 삭제 검증.

(a) 혼합 청크에서 --apply 시 충돌 유발 라인만 삭제되고 무관 규칙 보존.
(b) b_lines 없는 혼합 청크(구버전 리포트)는 여전히 보수 제외.
(c) 스테일(파일 변경) 시 거부 유지.
(d) 단일 규칙 청크 회귀 없음.
(e) restore 로 라인 삭제 복구 가능.
"""
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rune.cli.main import app
from rune.review.applier import Operation, StaleChunkError, apply_operations
from rune.review.cli import _build_apply_ops
from rune.review.types import ChunkRef, ConflictPair

runner = CliRunner()


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _ref(path, text: str, start: int = 1, end: int = None) -> ChunkRef:
    lines = text.splitlines()
    end = end if end is not None else start + max(len(lines) - 1, 0)
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
# (a) 혼합 청크 라인 정밀 삭제 — 유발 라인만 제거, 무관 규칙 보존
# ===========================================================================

class TestLinePrecisionApply:
    """혼합 청크에서 충돌 유발 라인(b_lines)만 삭제되고 무관 규칙이 보존된다."""

    def test_delete_lines_removes_only_matching_line(self, tmp_path):
        """delete_lines op 는 line_range 라인만 삭제한다."""
        # 파일: 3줄 (1: 충돌 유발, 2: 무관 규칙, 3: 무관 규칙)
        content = "Never use spaces.\nUse 4-space indent.\nUse LF line endings.\n"
        f = tmp_path / "rules.md"
        f.write_text(content)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=3,
            sha256=_sha(content),
            text=content,
        )
        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete_lines", ref=ref, line_range=(1, 1))
        apply_operations([op], backup_dir=backup, base_root=tmp_path)

        result = f.read_text()
        # 첫 줄(Never use spaces.)은 제거
        assert "Never use spaces." not in result
        # 나머지 줄은 보존
        assert "Use 4-space indent." in result
        assert "Use LF line endings." in result

    def test_delete_lines_multi_line_range(self, tmp_path):
        """line_range 가 복수 라인을 지정하면 해당 범위만 삭제된다."""
        content = "Line1\nLine2\nLine3\nLine4\n"
        f = tmp_path / "rules.md"
        f.write_text(content)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=4,
            sha256=_sha(content),
            text=content,
        )
        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete_lines", ref=ref, line_range=(2, 3))
        apply_operations([op], backup_dir=backup, base_root=tmp_path)

        result = f.read_text()
        assert "Line1" in result
        assert "Line2" not in result
        assert "Line3" not in result
        assert "Line4" in result

    def test_cli_mixed_chunk_only_conflict_line_removed(self, tmp_path):
        """CLI --apply: 혼합 청크에서 충돌 유발 라인만 제거, 무관 규칙 보존.

        파일 b: 'Never use spaces.' (충돌 유발) + 'Use 4-space indent.' (무관)
        스캔 후 라인 정밀 삭제 → 'Never use spaces.' 제거, 'Use 4-space indent.' 잔존.
        """
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")

        result = _invoke_apply(tmp_path)
        assert result.exit_code == 0, result.output

        b_text = b.read_text()
        # 충돌 유발 라인은 제거
        assert "Never use spaces." not in b_text, "충돌 유발 라인이 잔존함"
        # 무관 규칙은 보존
        assert "Use 4-space indent." in b_text, "무관 규칙 라인이 소실됨"

    def test_cli_line_precision_message_appears(self, tmp_path):
        """라인 정밀 삭제 적용 시 stderr 에 안내 메시지가 출력된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")

        result = _invoke_apply(tmp_path)
        combined = result.output or ""
        assert "라인 정밀 삭제" in combined, f"라인 정밀 삭제 안내 없음: {combined!r}"

    def test_build_apply_ops_mixed_with_b_lines_creates_delete_lines(self):
        """b_lines 있는 혼합 청크 → delete_lines op 생성 (보수 제외 아님)."""
        mixed_text = "Never use spaces.\nUse 4-space indent.\n"
        b = _ref("b.md", mixed_text, start=5, end=6)
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=b,
            reason="r", confidence=0.95, source="lexical",
            b_lines=(5, 5),  # 충돌 유발 라인 지정
        )
        ops, _, prot_skip, _, lp = _build_apply_ops([high], [])
        # 라인 정밀 삭제 op 1건 생성, 보수 제외 0건
        assert lp == 1
        assert prot_skip == 0
        assert len(ops) == 1
        assert ops[0].kind == "delete_lines"
        assert ops[0].line_range == (5, 5)

    def test_operation_log_records_line_range(self, tmp_path):
        """delete_lines op 의 operation_log 에 line_range 가 기록된다."""
        content = "Never use spaces.\nUse 4-space indent.\nUse LF.\n"
        f = tmp_path / "rules.md"
        f.write_text(content)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=3,
            sha256=_sha(content),
            text=content,
        )
        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete_lines", ref=ref, line_range=(1, 1))
        log = apply_operations([op], backup_dir=backup, base_root=tmp_path)

        # operation_log 에 line_range 포함 여부 확인
        assert len(log["ops"]) == 1
        op_entry = log["ops"][0]
        assert op_entry["kind"] == "delete_lines"
        assert op_entry["line_range"] == [1, 1]


# ===========================================================================
# (b) b_lines 없는 혼합 청크(구버전 리포트)는 보수 제외
# ===========================================================================

class TestLinePrecisionFallback:
    """b_lines=None 인 혼합 청크는 v0.2 보수 경로(제외)를 유지한다."""

    def test_mixed_chunk_without_b_lines_excluded(self):
        """b_lines=None 혼합 청크 → 보수 제외(protected_skipped 증가)."""
        mixed_text = "Use spaces.\nUse 4-space indent.\n"
        b = _ref("b.md", mixed_text)
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=b,
            reason="r", confidence=0.95, source="lexical",
            b_lines=None,
        )
        ops, _, prot_skip, _, lp = _build_apply_ops([high], [])
        assert prot_skip == 1
        assert lp == 0
        assert ops == []

    def test_from_report_without_b_lines_excluded(self, tmp_path):
        """--from-report 구버전 리포트(b_lines 필드 없음) → 혼합 청크 보수 제외."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")
        before_b = b.read_text()

        sha_a = hashlib.sha256("Always use spaces.".encode()).hexdigest()
        sha_b = hashlib.sha256(before_b.strip().encode()).hexdigest()

        # b_lines 필드 없는 구버전 리포트
        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1, "sha256": sha_a},
                "b": {"path": str(b), "start_line": 1, "end_line": 2, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
                # b_lines 필드 없음 → None → 보수 제외
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
        # 구버전 리포트(b_lines 없음) → 혼합 청크 보수 제외 → 파일 변경 없음
        assert b.read_text() == before_b, "구버전 리포트의 혼합 청크가 수정되었음"

    def test_from_report_with_b_lines_applies_line_precision(self, tmp_path):
        """--from-report 신버전 리포트(b_lines 있음) → 혼합 청크에 라인 정밀 삭제."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        a = _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")
        before_b = b.read_text()

        sha_a = hashlib.sha256("Always use spaces.".encode()).hexdigest()
        sha_b = hashlib.sha256(before_b.strip().encode()).hexdigest()

        # b_lines 필드 있는 신버전 리포트 — 1번 줄(Never use spaces.)이 유발 라인
        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": str(a), "start_line": 1, "end_line": 1, "sha256": sha_a},
                "b": {"path": str(b), "start_line": 1, "end_line": 2, "sha256": sha_b},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
                "b_lines": [1, 1],  # 신버전: b_lines 있음
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
        # 라인 정밀 삭제: 충돌 유발 라인 제거, 무관 규칙 보존
        b_text = b.read_text()
        assert "Never use spaces." not in b_text, "충돌 유발 라인이 잔존함"
        assert "Use 4-space indent." in b_text, "무관 규칙 라인이 소실됨"


# ===========================================================================
# (c) 스테일(파일 변경) 시 거부 유지
# ===========================================================================

class TestStaleRejection:
    """delete_lines op 도 sha256 스테일 검증에서 거부된다."""

    def test_delete_lines_stale_chunk_raises(self, tmp_path):
        """delete_lines op: 파일이 스캔 이후 변경되면 StaleChunkError."""
        original = "Never use spaces.\nUse 4-space indent.\n"
        f = tmp_path / "rules.md"
        f.write_text(original)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=2,
            sha256=_sha(original),
            text=original,
        )
        # 파일 변경 시 라인 수를 동일하게 유지해야 bounds check 이전에 stale 검증이 먼저 발동.
        # 라인 수가 줄면 bounds check(ValueError)가 먼저 터짐.
        f.write_text("Changed line one.\nChanged line two.\n")

        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete_lines", ref=ref, line_range=(1, 1))
        with pytest.raises(StaleChunkError):
            apply_operations([op], backup_dir=backup, base_root=tmp_path)

    def test_delete_stale_chunk_still_raises(self, tmp_path):
        """기존 delete op 도 스테일 검증은 변함없이 동작한다(회귀 없음)."""
        original = "Never use spaces.\n"
        f = tmp_path / "rules.md"
        f.write_text(original)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=1,
            sha256=_sha(original),
            text=original,
        )
        f.write_text("Changed.\n")

        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete", ref=ref)
        with pytest.raises(StaleChunkError):
            apply_operations([op], backup_dir=backup, base_root=tmp_path)


# ===========================================================================
# (d) 단일 규칙 청크 회귀 없음
# ===========================================================================

class TestSingleRuleRegression:
    """단일 규칙 청크는 기존 delete op 경로 그대로 전체 삭제된다."""

    def test_single_rule_chunk_full_delete(self, tmp_path):
        """단일 규칙 청크는 delete op 로 전체 제거된다."""
        content = "Never use spaces.\n"
        f = tmp_path / "rules.md"
        f.write_text(content)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=1,
            sha256=_sha(content),
            text=content,
        )
        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete", ref=ref)
        apply_operations([op], backup_dir=backup, base_root=tmp_path)

        assert f.read_text() == "", "단일 규칙이 완전히 삭제되지 않음"

    def test_build_apply_ops_single_rule_creates_delete_not_delete_lines(self):
        """단일 규칙 청크는 _build_apply_ops 에서 delete op 를 생성한다."""
        b = _ref("b.md", "Never use spaces.")
        high = ConflictPair(
            a=_ref("a.md", "Always use spaces."),
            b=b,
            reason="r", confidence=0.95, source="lexical",
        )
        ops, _, prot_skip, _, lp = _build_apply_ops([high], [])
        assert prot_skip == 0
        assert lp == 0
        assert len(ops) == 1
        # 단일 규칙 → delete (delete_lines 아님)
        assert ops[0].kind == "delete"

    def test_cli_single_rule_fully_deleted(self, tmp_path):
        """CLI --apply: 단일 규칙 파일은 내용이 완전히 삭제된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\n")

        result = _invoke_apply(tmp_path)
        assert result.exit_code == 0, result.output
        # 단일 규칙 파일은 비어 있어야 함
        assert b.read_text().strip() == "", "단일 규칙이 삭제되지 않음"


# ===========================================================================
# (e) restore 로 라인 삭제 복구 가능
# ===========================================================================

class TestRestoreAfterLineDelete:
    """delete_lines op 적용 후 --restore 로 원본 복구가 가능하다."""

    def test_restore_after_delete_lines(self, tmp_path):
        """delete_lines 후 --restore 로 원본 내용이 복구된다."""
        original = "Never use spaces.\nUse 4-space indent.\n"
        f = tmp_path / "rules.md"
        f.write_text(original)

        ref = ChunkRef(
            path=f,
            start_line=1,
            end_line=2,
            sha256=_sha(original),
            text=original,
        )
        backup = tmp_path / ".rune" / "backups"
        op = Operation(kind="delete_lines", ref=ref, line_range=(1, 1))
        log = apply_operations([op], backup_dir=backup, base_root=tmp_path)

        # delete_lines 후 파일 변경 확인
        assert "Never use spaces." not in f.read_text()

        # --restore 로 복구
        snapshot_ts = log["timestamp"]
        result = runner.invoke(
            app,
            ["review", str(tmp_path), "--restore", snapshot_ts],
        )
        assert result.exit_code == 0, result.output

        # 원본 복구 확인
        restored = f.read_text()
        assert "Never use spaces." in restored, "restore 후 삭제된 라인이 복구되지 않음"
        assert "Use 4-space indent." in restored, "restore 후 무관 라인이 소실됨"

    def test_cli_restore_after_apply(self, tmp_path):
        """CLI --apply → --restore 흐름에서 라인 삭제가 복구된다."""
        (tmp_path / "CLAUDE.md").write_text("# P\n\nCore rules apply.\n")
        _write_rule(tmp_path, "modal_a.md", "Always use spaces.\n")
        b = _write_rule(tmp_path, "modal_b.md", "Never use spaces.\nUse 4-space indent.\n")
        before_b = b.read_text()

        # apply
        apply_result = _invoke_apply(tmp_path, "--json")
        assert apply_result.exit_code == 0, apply_result.output

        # 적용 후 변경 확인 (라인 정밀 삭제)
        assert "Never use spaces." not in b.read_text()

        # 스냅샷 타임스탬프 추출: 백업 디렉토리에서 직접 확인(출력 파싱보다 안정적).
        backup_root = tmp_path / ".rune" / "backups"
        snapshots = sorted([p for p in backup_root.iterdir() if p.is_dir()],
                           key=lambda p: p.stat().st_mtime)
        assert snapshots, "백업 스냅샷이 생성되지 않음"
        snapshot_ts = snapshots[-1].name

        # restore
        restore_result = runner.invoke(
            app,
            ["review", str(tmp_path), "--restore", snapshot_ts],
        )
        assert restore_result.exit_code == 0, restore_result.output

        # 복구 확인
        assert b.read_text() == before_b, "restore 후 원본 내용이 복구되지 않음"


# ===========================================================================
# (f) b_lines to_dict / from_json 라운드트립
# ===========================================================================

class TestBLinesSchema:
    """ConflictPair.b_lines 는 to_dict() 에 additive 포함되고 JSON 파싱 시 복원된다."""

    def test_to_dict_includes_b_lines_when_set(self):
        from rune.review.types import ConflictPair, ChunkRef
        from pathlib import Path
        a = ChunkRef(path=Path("a.md"), start_line=1, end_line=1,
                     sha256="aaa", text="Always use spaces.")
        b = ChunkRef(path=Path("b.md"), start_line=5, end_line=6,
                     sha256="bbb", text="Never use spaces.\nUse 4-space indent.")
        cp = ConflictPair(a=a, b=b, reason="r", confidence=0.95,
                          source="lexical", b_lines=(5, 5))
        d = cp.to_dict()
        assert "b_lines" in d
        assert d["b_lines"] == [5, 5]

    def test_to_dict_omits_b_lines_when_none(self):
        from rune.review.types import ConflictPair, ChunkRef
        from pathlib import Path
        a = ChunkRef(path=Path("a.md"), start_line=1, end_line=1, sha256="aaa", text="x")
        b = ChunkRef(path=Path("b.md"), start_line=1, end_line=1, sha256="bbb", text="y")
        cp = ConflictPair(a=a, b=b, reason="r", confidence=0.95,
                          source="lexical", b_lines=None)
        d = cp.to_dict()
        assert "b_lines" not in d

    def test_load_report_parses_b_lines(self, tmp_path):
        from rune.review.cli import _load_report_from_json
        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": "a.md", "start_line": 1, "end_line": 1, "sha256": "aaa"},
                "b": {"path": "b.md", "start_line": 5, "end_line": 6, "sha256": "bbb"},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
                "b_lines": [5, 5],
            }],
            "dead_candidates": [],
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report_data))
        report = _load_report_from_json(f)
        assert len(report.conflicts) == 1
        assert report.conflicts[0].b_lines == (5, 5)

    def test_load_report_b_lines_none_when_absent(self, tmp_path):
        from rune.review.cli import _load_report_from_json
        report_data = {
            "schema_version": "1.0", "detector_tier": "L1",
            "conflicts": [{
                "a": {"path": "a.md", "start_line": 1, "end_line": 1, "sha256": "aaa"},
                "b": {"path": "b.md", "start_line": 1, "end_line": 1, "sha256": "bbb"},
                "reason": "modal", "confidence": 0.95, "source": "lexical",
                # b_lines 없음 → None
            }],
            "dead_candidates": [],
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report_data))
        report = _load_report_from_json(f)
        assert report.conflicts[0].b_lines is None
