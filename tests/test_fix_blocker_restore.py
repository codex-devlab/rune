"""--restore 가 하위 디렉토리 파일을 정상 복구하는지 검증.

버그: snap.iterdir() 는 평면 순회라 .claude/rules/* 같이 하위 디렉토리에
백업된 파일을 놓쳐 IsADirectoryError 크래시 또는 복구 누락이 발생했다.
수정: rglob('*') 재귀 순회 + target.parent.mkdir(parents=True, exist_ok=True).
"""
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from rune.review.cli import review_app

runner = CliRunner()


def _make_snapshot(backup_root: Path, timestamp: str, files: dict[str, bytes]) -> Path:
    """백업 스냅샷 디렉토리를 인위적으로 생성한다.

    files: {상대경로문자열: 바이트내용} — operation_log.json 은 자동 생성.
    """
    snap = backup_root / timestamp
    snap.mkdir(parents=True)
    for rel, data in files.items():
        dst = snap / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    log = {"timestamp": timestamp, "ops": []}
    (snap / "operation_log.json").write_text(json.dumps(log))
    return snap


# ---------------------------------------------------------------------------
# 핵심 수정 검증: 하위 디렉토리 파일 복구
# ---------------------------------------------------------------------------

def test_restore_subdirectory_file(tmp_path: Path):
    """.claude/rules/python.md 처럼 하위 디렉토리 파일이 정상 복구되어야 한다."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    backup_root = project_dir / ".rune" / "backups"

    timestamp = "20260101T000000Z"
    original_content = b"# Python rules\nUse spaces.\n"

    # 스냅샷에 하위 디렉토리 파일 포함
    _make_snapshot(backup_root, timestamp, {
        ".claude/rules/python.md": original_content,
    })

    # 현재 프로젝트에는 파일이 없는 상태(apply 후 삭제된 상황 시뮬레이션)
    result = runner.invoke(review_app, ["--restore", timestamp, str(project_dir)])

    assert result.exit_code == 0, f"restore 크래시: {result.output}\n{result.exception}"
    restored = project_dir / ".claude" / "rules" / "python.md"
    assert restored.exists(), "하위 디렉토리 파일이 복구되어야 한다"
    assert restored.read_bytes() == original_content, "복구된 내용이 원본과 일치해야 한다"


def test_restore_mixed_depth_files(tmp_path: Path):
    """최상위 파일과 하위 디렉토리 파일이 혼재할 때 모두 복구되어야 한다."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    backup_root = project_dir / ".rune" / "backups"

    timestamp = "20260101T000001Z"
    top_content = b"# Top level rule\n"
    sub_content = b"# Nested rule\n"

    _make_snapshot(backup_root, timestamp, {
        "CLAUDE.md": top_content,
        ".claude/rules/golang.md": sub_content,
    })

    result = runner.invoke(review_app, ["--restore", timestamp, str(project_dir)])

    assert result.exit_code == 0, f"restore 크래시: {result.output}\n{result.exception}"

    top_file = project_dir / "CLAUDE.md"
    sub_file = project_dir / ".claude" / "rules" / "golang.md"
    assert top_file.exists() and top_file.read_bytes() == top_content, \
        "최상위 파일 복구 회귀 없어야 한다"
    assert sub_file.exists() and sub_file.read_bytes() == sub_content, \
        "하위 디렉토리 파일이 복구되어야 한다"


def test_restore_operation_log_skipped(tmp_path: Path):
    """operation_log.json 은 복구 대상에서 제외되어야 한다."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    backup_root = project_dir / ".rune" / "backups"

    timestamp = "20260101T000002Z"
    _make_snapshot(backup_root, timestamp, {
        "CLAUDE.md": b"# rule\n",
    })

    result = runner.invoke(review_app, ["--restore", timestamp, str(project_dir)])
    assert result.exit_code == 0

    # operation_log.json 이 프로젝트 루트에 복원되면 안 된다.
    assert not (project_dir / "operation_log.json").exists(), \
        "operation_log.json 은 복구 대상에서 제외되어야 한다"


def test_restore_snapshot_not_found(tmp_path: Path):
    """존재하지 않는 스냅샷 이름은 exit code 2 로 실패해야 한다."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    result = runner.invoke(review_app, ["--restore", "nonexistent", str(project_dir)])
    assert result.exit_code == 2, "존재하지 않는 스냅샷은 exit 2 여야 한다"


# ---------------------------------------------------------------------------
# 회귀: 최상위 파일 복구가 여전히 동작하는지 확인
# ---------------------------------------------------------------------------

def test_restore_top_level_file_regression(tmp_path: Path):
    """기존 동작(최상위 파일 복구)이 재귀 순회 변경 후에도 유지되어야 한다."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    backup_root = project_dir / ".rune" / "backups"

    timestamp = "20260101T000003Z"
    content = b"# Original content\n"
    _make_snapshot(backup_root, timestamp, {"AGENTS.md": content})

    # 현재 파일을 다른 내용으로 덮어쓴 상태 시뮬레이션
    (project_dir / "AGENTS.md").write_bytes(b"# Modified\n")

    result = runner.invoke(review_app, ["--restore", timestamp, str(project_dir)])
    assert result.exit_code == 0

    restored = (project_dir / "AGENTS.md").read_bytes()
    assert restored == content, "최상위 파일이 원본 내용으로 복구되어야 한다"
