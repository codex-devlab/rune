import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from rune.review.types import ChunkRef, DeadCandidate


def find_dead_rules_events(
    refs: list[ChunkRef], events_path: Path, window_days: int = 30,
) -> list[DeadCandidate]:
    """Return chunks that have never fired according to events.jsonl.

    Args:
        refs: Chunk references to evaluate.
        events_path: Path to events.jsonl.
        window_days: Only consider events within this many days of now.
            Set to 0 to disable time filtering (all-time).
    """
    if not events_path.exists():
        return []

    cutoff: datetime | None = None
    if window_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    fired: set[str] = set()
    skipped_no_timestamp = 0
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        sha = ev.get("chunk_sha")
        count = ev.get("applied_count", 0)
        if not sha or count <= 0:
            continue

        if cutoff is not None:
            ts_str = ev.get("timestamp") or ev.get("ts") or ev.get("applied_at")
            if ts_str is None:
                skipped_no_timestamp += 1
                continue  # untimestamped events excluded from windowed analysis
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                skipped_no_timestamp += 1
                continue
            if ts < cutoff:
                continue

        fired.add(sha)

    return [
        DeadCandidate(chunk=r, reason="never fired in events.jsonl", stage="events")
        for r in refs if r.sha256 not in fired
    ]
