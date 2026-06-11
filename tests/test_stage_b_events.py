import json
from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.dead_events import find_dead_rules_events


def test_chunk_in_events_is_alive(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"chunk_sha": "abc", "applied_count": 3}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events)
    assert dead == []


def test_chunk_not_in_events_is_dead(tmp_path):
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    ref = ChunkRef(path=target, start_line=1, end_line=1, sha256="abc", text="Always use TS.")
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"chunk_sha": "xxx", "applied_count": 1}) + "\n")
    dead = find_dead_rules_events([ref], events_path=events)
    assert len(dead) == 1
    assert dead[0].stage == "events"
