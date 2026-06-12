import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.dead_events import find_dead_rules_events


def test_chunk_in_events_is_alive(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 3, "ts": recent_ts}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events)
    assert dead == []


def test_chunk_not_in_events_is_dead(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    events.write_text(json.dumps({"chunk_sha": "xxx", "applied_count": 1, "ts": recent_ts}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events)
    assert len(dead) == 1
    assert dead[0].stage == "events"


def test_events_within_window_keep_chunk_alive(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 1, "timestamp": recent_ts}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events, window_days=30)
    assert dead == []  # alive (within window)


def test_events_outside_window_mark_chunk_dead(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 1, "timestamp": old_ts}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events, window_days=30)
    assert len(dead) == 1
    assert dead[0].stage == "events"


def test_window_zero_disables_filtering(tmp_path):
    """window_days=0 means: don't filter by time."""
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=9999)).isoformat()
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 1, "timestamp": old_ts}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events, window_days=0)
    assert dead == []  # alive even with ancient event (window disabled)


def test_untimestamped_events_treated_as_dead_when_windowed(tmp_path):
    """An event without timestamp can't be confirmed within window → chunk treated as dead."""
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 1}) + "\n")  # NO timestamp
    dead = find_dead_rules_events([ref], events_path=events, window_days=30)
    assert len(dead) == 1
