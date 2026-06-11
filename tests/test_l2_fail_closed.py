import subprocess, os


def test_l2_fails_closed_without_cache_and_without_flag(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\nNever use TS.\n")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    # Also set HF_HOME to nonexistent dir so cache check fails
    monkeypatch.setenv("HF_HOME", str(tmp_path / "fake_hf_home"))
    result = subprocess.run(
        ["rune", "review", "--l2", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "huggingface-cli download" in result.stderr or "huggingface-cli download" in result.stdout
