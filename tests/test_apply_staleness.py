import hashlib
from pathlib import Path
import pytest
from rune.review.types import ChunkRef
from rune.review.applier import apply_operations, Operation, StaleChunkError

def test_apply_refuses_stale_chunk(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("line1\nAlways use TS.\nline3\n")
    text = "Always use TS."
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref = ChunkRef(path=target, start_line=2, end_line=2, sha256=sha, text=text)
    # Mutate the file externally
    target.write_text("line1\nNever use TS.\nline3\n")
    with pytest.raises(StaleChunkError):
        apply_operations([Operation(kind="delete", ref=ref)], backup_dir=tmp_path / "bk")

def test_apply_deletes_chunk(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("line1\nAlways use TS.\nline3\n")
    text = "Always use TS."
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref = ChunkRef(path=target, start_line=2, end_line=2, sha256=sha, text=text)
    apply_operations([Operation(kind="delete", ref=ref)], backup_dir=tmp_path / "bk")
    assert "Always use TS" not in target.read_text()
    assert (tmp_path / "bk").exists()
