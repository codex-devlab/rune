import hashlib
import pytest
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.applier import apply_operations, Operation


def test_apply_rejects_out_of_bounds(tmp_path):
    """I5: chunk with end_line > file length raises ValueError"""
    target = tmp_path / "rule.md"
    target.write_text("line1\nline2\n")
    text = "line2"
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref = ChunkRef(path=target, start_line=2, end_line=99, sha256=sha, text=text)
    with pytest.raises(ValueError, match="out of bounds"):
        apply_operations(
            [Operation(kind="delete", ref=ref)],
            backup_dir=tmp_path / "bk",
            base_root=tmp_path,
        )


def test_backup_preserves_relative_path(tmp_path):
    """C3: two files with same basename in different subdirs both back up correctly"""
    (tmp_path / "subdir").mkdir()
    f1 = tmp_path / "CLAUDE.md"
    f2 = tmp_path / "subdir" / "CLAUDE.md"
    text = "rule"
    f1.write_text(text + "\n")
    f2.write_text(text + "\n")
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref1 = ChunkRef(path=f1, start_line=1, end_line=1, sha256=sha, text=text)
    ref2 = ChunkRef(path=f2, start_line=1, end_line=1, sha256=sha, text=text)
    backup_dir = tmp_path / "bk"
    apply_operations(
        [Operation(kind="delete", ref=ref1), Operation(kind="delete", ref=ref2)],
        backup_dir=backup_dir,
        base_root=tmp_path,
    )
    # Find the snapshot dir
    snaps = list(backup_dir.iterdir())
    assert len(snaps) == 1
    snap = snaps[0]
    # Both backups should exist under their relative paths
    assert (snap / "CLAUDE.md").exists()
    assert (snap / "subdir" / "CLAUDE.md").exists()
