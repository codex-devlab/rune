import hashlib
from pathlib import Path
from rune.pipeline.inventory import run_inventory
from rune.review.types import ChunkRef


def load_chunk_refs(repo_root: Path) -> list[tuple[ChunkRef, str]]:
    sources, _ = run_inventory(repo_root)
    refs: list[tuple[ChunkRef, str]] = []
    for s in sources:
        for c in s.chunks:
            sha = hashlib.sha256(c.text.encode("utf-8")).hexdigest()
            ref = ChunkRef(
                path=s.path,
                start_line=c.start_line,
                end_line=c.end_line,
                sha256=sha,
                text=c.text,
            )
            refs.append((ref, getattr(s, "trigger", None) or ""))
    return refs
