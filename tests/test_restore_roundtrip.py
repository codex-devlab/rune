import subprocess
import json
from pathlib import Path


def test_apply_and_restore_roundtrip(tmp_path):
    target = tmp_path / "CLAUDE.md"
    original = "# Section A\n\nAlways use TS.\n\n# Section B\n\nNever use TS.\n"
    target.write_text(original)
    # Apply (headless heuristic: delete the b-side of every conflict)
    result = subprocess.run(
        ["rune", "review", "--apply", "--yes", "--confirm-delete-heuristics", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"apply failed: {result.stderr}"
    assert target.read_text() != original
    # Find latest backup
    backups = sorted((tmp_path / ".rune" / "backups").iterdir())
    assert len(backups) >= 1
    latest = backups[-1].name
    result = subprocess.run(
        ["rune", "review", "--restore", latest, str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"restore failed: {result.stderr}"
    assert target.read_text() == original
