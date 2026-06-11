import json
from pathlib import Path
from rune.review.types import ChunkRef, DeadCandidate


def find_dead_rules_events(
    refs: list[ChunkRef], events_path: Path, window_days: int = 30,
) -> list[DeadCandidate]:
    """Return chunks that have never fired according to events.jsonl.

    window_days is accepted but not yet used for filtering — v0.2 stub;
    full windowing in v0.3.
    """
    if not events_path.exists():
        return []
    fired: set[str] = set()
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        sha = ev.get("chunk_sha")
        count = ev.get("applied_count", 0)
        if sha and count > 0:
            fired.add(sha)
    return [
        DeadCandidate(chunk=r, reason="never fired in events.jsonl", stage="events")
        for r in refs if r.sha256 not in fired
    ]
