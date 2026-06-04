import pytest
from pathlib import Path
from rune.adapters.base import Platform, detect_platform
from rune.adapters.claude_code import ClaudeCodeAdapter
from rune.adapters.generic import GenericAdapter
from rune.adapters.cursor import CursorAdapter
from rune.adapters.copilot import CopilotAdapter
from rune.adapters.gemini import GeminiAdapter
from rune.adapters.windsurf import WindsurfAdapter
from rune.pipeline.inventory import run_inventory


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


# ─── Copilot ──────────────────────────────────────────────────────────────────

def test_detect_copilot_by_instructions(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("# Copilot rules")
    assert detect_platform(tmp_path) == Platform.COPILOT


def test_copilot_adapter_detect(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("# rules")
    assert CopilotAdapter().detect(tmp_path) is True


def test_copilot_adapter_detect_false(tmp_path):
    assert CopilotAdapter().detect(tmp_path) is False


def test_copilot_adapter_finds_instructions(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text(
        "Always add docstrings to public methods."
    )
    sources = CopilotAdapter().list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "copilot_instructions"
    assert sources[0].token_count > 0


def test_copilot_adapter_finds_rules_dir(tmp_path):
    rules = tmp_path / ".github" / "copilot"
    rules.mkdir(parents=True)
    (rules / "python.md").write_text("Use type hints.")
    (rules / "testing.md").write_text("Use pytest.")
    sources = CopilotAdapter().list_sources(tmp_path)
    assert len(sources) == 2
    assert all(s.source_type == "copilot_rule" for s in sources)


# ─── Gemini ───────────────────────────────────────────────────────────────────

def test_detect_gemini_by_file(tmp_path):
    (tmp_path / "GEMINI.md").write_text("# Gemini rules")
    assert detect_platform(tmp_path) == Platform.GEMINI


def test_detect_gemini_by_dir(tmp_path):
    (tmp_path / ".gemini").mkdir()
    assert detect_platform(tmp_path) == Platform.GEMINI


def test_gemini_adapter_finds_gemini_md(tmp_path):
    (tmp_path / "GEMINI.md").write_text("Be concise and helpful.")
    sources = GeminiAdapter().list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "gemini_md"


def test_gemini_adapter_finds_rules_dir(tmp_path):
    gemini_dir = tmp_path / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "rules.md").write_text("Follow coding standards.")
    sources = GeminiAdapter().list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "gemini_rule"


# ─── Windsurf ─────────────────────────────────────────────────────────────────

def test_detect_windsurf(tmp_path):
    (tmp_path / ".windsurfrules").write_text("# Windsurf rules")
    assert detect_platform(tmp_path) == Platform.WINDSURF


def test_windsurf_adapter_finds_rules(tmp_path):
    (tmp_path / ".windsurfrules").write_text("Always use strict TypeScript.")
    sources = WindsurfAdapter().list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "windsurf_rules"


def test_windsurf_adapter_empty_no_crash(tmp_path):
    assert WindsurfAdapter().list_sources(tmp_path) == []


# ─── Multi-platform ───────────────────────────────────────────────────────────

def test_multi_platform_no_dedup(tmp_path):
    """Project with both Claude Code and Copilot should return sources from both."""
    (tmp_path / "CLAUDE.md").write_text("# Claude rules")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("# Copilot rules")
    sources, platform = run_inventory(tmp_path)
    types = {s.source_type for s in sources}
    assert "claude_md" in types
    assert "copilot_instructions" in types
    assert platform == Platform.CLAUDE_CODE  # Claude Code wins as primary


def test_multi_platform_dedup(tmp_path):
    """Same file must not appear twice even if two adapters would list it."""
    (tmp_path / "GEMINI.md").write_text("# Gemini and generic")
    sources, _ = run_inventory(tmp_path)
    paths = [s.path for s in sources]
    assert len(paths) == len(set(paths))  # no duplicates
