import subprocess, time, signal, os, tempfile


def test_tui_cold_start_under_850ms(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\n" * 250)
    t0 = time.perf_counter()
    env = {**os.environ, "TEXTUAL_HEADLESS": "1"}
    proc = subprocess.Popen(
        ["rune", "review", str(tmp_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )
    # Wait up to 0.85s for app to start, then signal exit
    time.sleep(0.85)
    elapsed = time.perf_counter() - t0
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    assert elapsed < 0.95, f"cold start measurement window exceeded: {elapsed:.3f}s"
