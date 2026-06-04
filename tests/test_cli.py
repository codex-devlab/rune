import json
from typer.testing import CliRunner
from rune.cli.main import app

runner = CliRunner()


def test_analyze_empty_project(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert result.exit_code == 0
    assert "설정 없음" in result.output or "No config" in result.output


def test_analyze_minimal_project(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project)])
    assert result.exit_code == 0
    assert "token" in result.output.lower() or "토큰" in result.output


def test_analyze_complex_project(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project)])
    assert result.exit_code == 0
    assert any(x in result.output for x in ["token", "토큰", "중복", "dedup"])


def test_analyze_current_dir_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# test")
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 0


def test_analyze_json_flag(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "total_tokens" in data


def test_init_creates_claude_md(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()


def test_init_creates_rules_dir(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    assert (tmp_path / ".claude" / "rules").is_dir()


def test_scaffold_python_backend(tmp_path):
    result = runner.invoke(app, ["scaffold", "--type", "python-backend", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".claude" / "rules").is_dir()


def test_scaffold_unknown_type_exits_gracefully(tmp_path):
    result = runner.invoke(app, ["scaffold", "--type", "unknown-xyz", str(tmp_path)])
    assert result.exit_code == 0  # graceful, not crash


def test_watch_creates_events_file(tmp_path, monkeypatch):
    events_file = tmp_path / "events.jsonl"
    from rune.cli import watch as watch_module
    monkeypatch.setattr(watch_module, "_collect_event", lambda p: {
        "session_id": "test",
        "sources_loaded": [],
        "trigger_matched": None,
    })
    watch_module.append_event(events_file, {"session_id": "test"})
    assert events_file.exists()
    line = events_file.read_text().strip()
    data = json.loads(line)
    assert "session_id" in data
