"""
E2E benchmark tests — validate core invariants across all user levels.
"""
import json
import time
from pathlib import Path
from typer.testing import CliRunner
from rune.cli.main import app

runner = CliRunner()


# ─── Benchmark-0: Empty project ───────────────────────────────────────────────

def test_benchmark0_empty_no_crash(empty_project):
    """Empty project must exit 0, never crash."""
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert result.exit_code == 0, result.output


def test_benchmark0_empty_json_valid(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] == 0
    assert data["level"] == 0


def test_benchmark0_shows_guidance(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert "init" in result.output.lower()


# ─── Benchmark-1: Minimal project ─────────────────────────────────────────────

def test_benchmark1_minimal_reports_tokens(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] > 0
    assert data["level"] >= 1


def test_benchmark1_no_dedup_on_minimal(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    data = json.loads(result.output)
    assert data["dedup_high"] == 0


# ─── Benchmark-2: Complex project (pmo-vault-like) ────────────────────────────

def test_benchmark2_detects_tokens(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] > 100


def test_benchmark2_detects_duplicate(complex_project):
    """complex_project fixture has git.md and duplicate.md with identical content."""
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    data = json.loads(result.output)
    assert data["dedup_high"] >= 1, "Should detect at least 1 HIGH-confidence duplicate"


def test_benchmark2_level_3(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    data = json.loads(result.output)
    assert data["level"] >= 2


def test_benchmark2_completes_under_30_seconds(complex_project):
    start = time.time()
    result = runner.invoke(app, ["analyze", str(complex_project)])
    elapsed = time.time() - start
    assert result.exit_code == 0
    assert elapsed < 30, f"Took {elapsed:.1f}s — too slow"


# ─── Benchmark-0 for init ─────────────────────────────────────────────────────

def test_benchmark0_init_creates_structure(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".claude" / "rules").is_dir()
    result2 = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    data = json.loads(result2.output)
    assert data["level"] >= 1
