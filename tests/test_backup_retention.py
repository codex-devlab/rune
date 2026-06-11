import time
from pathlib import Path
from rune.review.applier import prune_backups

def test_prune_keeps_last_10(tmp_path):
    for i in range(15):
        (tmp_path / f"snap_{i:02d}").mkdir()
        time.sleep(0.005)
    prune_backups(tmp_path, keep=10)
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert len(remaining) == 10
    assert remaining == sorted([f"snap_{i:02d}" for i in range(5, 15)])


import subprocess
def test_11_apply_sessions_yields_10_snapshots(tmp_path):
    target = tmp_path / "CLAUDE.md"
    for i in range(11):
        target.write_text(f"# Section A\n\nAlways use X{i}.\n\n# Section B\n\nNever use X{i}.\n")
        result = subprocess.run(
            ["rune", "review", "--apply", "--yes", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"iter {i} failed: {result.stderr}"
        time.sleep(1.1)
    backups = sorted((tmp_path / ".rune" / "backups").iterdir())
    assert len(backups) == 10, f"expected 10, got {len(backups)}"
