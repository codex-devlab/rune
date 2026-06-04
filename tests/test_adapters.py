import pytest
from pathlib import Path
from rune.adapters.base import Platform, detect_platform
from rune.adapters.claude_code import ClaudeCodeAdapter
from rune.adapters.generic import GenericAdapter
from rune.adapters.cursor import CursorAdapter


def test_detect_claude_code_by_dot_claude(tmp_path):
    (tmp_path / ".claude").mkdir()
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE


def test_detect_claude_code_by_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# test")
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE


def test_detect_cursor(tmp_path):
    (tmp_path / ".cursor").mkdir()
    assert detect_platform(tmp_path) == Platform.CURSOR


def test_detect_cursor_by_rules_file(tmp_path):
    (tmp_path / ".cursorrules").write_text("# cursor rules")
    assert detect_platform(tmp_path) == Platform.CURSOR


def test_detect_generic_on_empty(tmp_path):
    assert detect_platform(tmp_path) == Platform.GENERIC


def test_claude_code_takes_priority_over_cursor(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE


def test_claude_code_adapter_empty_project(empty_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(empty_project)
    assert sources == []  # no crash on empty dir


def test_claude_code_adapter_finds_claude_md(minimal_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(minimal_project)
    types = [s.source_type for s in sources]
    assert "claude_md" in types


def test_claude_code_adapter_finds_rules(complex_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(complex_project)
    rule_sources = [s for s in sources if s.source_type == "rule"]
    assert len(rule_sources) >= 5


def test_claude_code_adapter_sources_have_tokens(complex_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(complex_project)
    assert all(s.token_count > 0 for s in sources)


def test_claude_code_adapter_detect(tmp_path):
    (tmp_path / ".claude").mkdir()
    adapter = ClaudeCodeAdapter()
    assert adapter.detect(tmp_path) is True


def test_claude_code_adapter_detect_false(tmp_path):
    adapter = ClaudeCodeAdapter()
    assert adapter.detect(tmp_path) is False


def test_generic_adapter_empty_project_no_crash(empty_project):
    adapter = GenericAdapter()
    sources = adapter.list_sources(empty_project)
    assert isinstance(sources, list)


def test_generic_adapter_finds_md_files(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Agent rules\n\nBe helpful.")
    adapter = GenericAdapter()
    sources = adapter.list_sources(tmp_path)
    assert len(sources) >= 1


def test_cursor_adapter_empty_no_crash(empty_project):
    adapter = CursorAdapter()
    sources = adapter.list_sources(empty_project)
    assert sources == []


def test_cursor_adapter_finds_cursorrules(tmp_path):
    (tmp_path / ".cursorrules").write_text("Always use TypeScript strict mode.")
    adapter = CursorAdapter()
    sources = adapter.list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "cursor_rules"
