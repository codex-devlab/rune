import hashlib
from pathlib import Path
import pytest
from rune.review.types import ChunkRef
from rune.review.applier import apply_operations, Operation, StaleChunkError
from rune.review.loader import load_chunk_refs

def test_apply_refuses_stale_chunk(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("line1\nAlways use TS.\n\nline3\n")
    text = "Always use TS."
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref = ChunkRef(path=target, start_line=2, end_line=2, sha256=sha, text=text)
    # Mutate the file externally
    target.write_text("line1\nNever use TS.\n\nline3\n")
    with pytest.raises(StaleChunkError):
        apply_operations([Operation(kind="delete", ref=ref)], backup_dir=tmp_path / "bk", base_root=tmp_path)

def test_apply_deletes_chunk(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("line1\nAlways use TS.\n\nline3\n")
    text = "Always use TS."
    sha = hashlib.sha256(text.encode()).hexdigest()
    ref = ChunkRef(path=target, start_line=2, end_line=2, sha256=sha, text=text)
    apply_operations([Operation(kind="delete", ref=ref)], backup_dir=tmp_path / "bk", base_root=tmp_path)
    assert "Always use TS" not in target.read_text()
    assert (tmp_path / "bk").exists()


def test_apply_refuses_stale_chunk_with_trailing_whitespace(tmp_path):
    """Regression test proving C1: applier's .rstrip('\\n') doesn't match producer's
    .strip(), so a chunk line with trailing spaces causes a false-positive StaleChunkError
    even on an unmodified file.

    Under buggy applier (rstrip('\\n') only):
      - loader sha  = sha256("Always use TS.")   [producer stripped trailing space]
      - applier sha = sha256("Always use TS. ")  [rstrip('\\n') leaves trailing space]
      → StaleChunkError raised on unmodified file → this test FAILS

    After Commit A (applier uses .strip()):
      - both sides produce sha256("Always use TS.")
      → no StaleChunkError → apply succeeds → this test PASSES
    """
    # The file contains a chunk line with trailing spaces.
    # The producer (tokenizer) will .strip() the paragraph, yielding "Always use TS."
    # but the file on disk still has the trailing space.
    # Use an agent-md name so the GenericAdapter's _walk_md picks it up.
    target = tmp_path / "CLAUDE.md"
    target.write_text("Always use TS. \n")

    # Use the real loader path to get the sha (routes through producer's .strip())
    refs_and_triggers = load_chunk_refs(tmp_path)
    assert refs_and_triggers, "loader found no chunks — check file layout"
    ref, _trigger = refs_and_triggers[0]

    # The file is UNMODIFIED since the scan.  A correct applier should succeed here.
    # Under the buggy applier the trailing space survives rstrip('\n'), causing a
    # sha mismatch and a spurious StaleChunkError.
    apply_operations([Operation(kind="delete", ref=ref)], backup_dir=tmp_path / "bk", base_root=tmp_path)
