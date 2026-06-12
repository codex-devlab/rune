"""Two-phase apply atomicity tests (#17)."""
import hashlib
import pytest
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.applier import apply_operations, Operation, StaleChunkError


def _ref(path: Path, text: str, line: int) -> ChunkRef:
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ChunkRef(path=path, start_line=line, end_line=line, sha256=sha, text=text)


def test_phase1_failure_leaves_no_tmp_files(tmp_path):
    """If staleness check fails on file #2, file #1 must not have been committed
    AND no .rune-apply-tmp must remain."""
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("Always use TS.\n")
    f2.write_text("Always use TS.\n")

    text = "Always use TS."
    ref1 = _ref(f1, text, 1)

    # Make ref2's sha NOT match — simulates stale
    ref2 = ChunkRef(
        path=f2, start_line=1, end_line=1,
        sha256="0" * 64,  # bogus sha
        text=text,
    )

    with pytest.raises(StaleChunkError):
        apply_operations(
            [Operation(kind="delete", ref=ref1), Operation(kind="delete", ref=ref2)],
            backup_dir=tmp_path / "bk", base_root=tmp_path,
        )

    # Verify NO target file changed
    assert f1.read_text() == "Always use TS.\n", "f1 should be untouched (Phase 1 failed)"
    assert f2.read_text() == "Always use TS.\n", "f2 should be untouched"

    # Verify NO .rune-apply-tmp files remain
    tmps = list(tmp_path.glob("*.rune-apply-tmp"))
    assert tmps == [], f"tmp files leaked: {tmps}"


def test_phase2_atomic_commit_all_files(tmp_path):
    """Successful apply commits ALL files. No tmp files left behind."""
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("Always use TS.\n")
    f2.write_text("Always use TS.\n")

    text = "Always use TS."
    ref1 = _ref(f1, text, 1)
    ref2 = _ref(f2, text, 1)

    apply_operations(
        [Operation(kind="delete", ref=ref1), Operation(kind="delete", ref=ref2)],
        backup_dir=tmp_path / "bk", base_root=tmp_path,
    )

    assert "Always use TS" not in f1.read_text()
    assert "Always use TS" not in f2.read_text()

    # No tmp files
    tmps = list(tmp_path.glob("*.rune-apply-tmp"))
    assert tmps == [], f"tmp files leaked after successful apply: {tmps}"

    # Backup contains both originals
    backups = list((tmp_path / "bk").iterdir())
    assert len(backups) == 1
    snap = backups[0]
    assert (snap / "a.md").exists()
    assert (snap / "b.md").exists()
