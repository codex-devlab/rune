from pathlib import Path
from rune.review.types import ChunkRef
from rune.review.dead_static import find_dead_rules_static


def test_dead_when_no_match(tmp_path):
    (tmp_path / "a.py").write_text("hello")
    ref = ChunkRef(
        path=tmp_path / "rule.md", start_line=1, end_line=2,
        sha256="x",
        text="Trigger: golang\nAlways gofmt before commit.",
    )
    dead = find_dead_rules_static([ref], repo_root=tmp_path)
    assert len(dead) == 1
    assert dead[0].stage == "static"


def test_alive_when_match(tmp_path):
    (tmp_path / "main.go").write_text("package main")
    ref = ChunkRef(
        path=tmp_path / "rule.md", start_line=1, end_line=2,
        sha256="x", text="Trigger: golang\nAlways gofmt.",
    )
    dead = find_dead_rules_static([ref], repo_root=tmp_path)
    assert dead == []
