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
