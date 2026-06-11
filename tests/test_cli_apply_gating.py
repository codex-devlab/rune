import subprocess
import json
import os
from pathlib import Path


def test_apply_yes_requires_confirmation(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# A\n\nAlways use X.\n\n# B\n\nNever use X.\n")
    result = subprocess.run(
        ["rune", "review", "--apply", "--yes", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "explicit confirmation" in result.stderr or "Refusing" in result.stderr


def test_apply_with_confirm_flag(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# A\n\nAlways use X.\n\n# B\n\nNever use X.\n")
    result = subprocess.run(
        ["rune", "review", "--apply", "--yes", "--confirm-delete-heuristics", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_apply_with_env_escape(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# A\n\nAlways use X.\n\n# B\n\nNever use X.\n")
    env = {**os.environ, "RUNE_ALLOW_BLIND_APPLY": "1"}
    result = subprocess.run(
        ["rune", "review", "--apply", "--yes", str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr


def test_apply_and_restore_mutex(tmp_path):
    result = subprocess.run(
        ["rune", "review", "--apply", "--restore", "20260611T000000Z", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "mutually exclusive" in result.stderr


def test_apply_json_identity(tmp_path):
    """I7: stdout JSON must equal operation_log.json byte-content (after pretty-print parse)"""
    (tmp_path / "CLAUDE.md").write_text("# A\n\nAlways use X.\n\n# B\n\nNever use X.\n")
    result = subprocess.run(
        ["rune", "review", "--apply", "--yes", "--confirm-delete-heuristics", "--json", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    stdout_data = json.loads(result.stdout)
    # Find the latest snapshot
    snapshots = sorted((tmp_path / ".rune" / "backups").iterdir())
    log_file = snapshots[-1] / "operation_log.json"
    disk_data = json.loads(log_file.read_text())
    assert stdout_data == disk_data
