"""Cold-start measurement for `rune review` TUI path."""
import os
import subprocess
import time
from pathlib import Path


def test_tui_cold_start_under_800ms(tmp_path):
    """Spec budget: ≤800ms from `rune review` invocation to TUI mount-ready."""
    # Larger fixture: 250 chunks worth of rules to exercise the scanning path
    (tmp_path / "CLAUDE.md").write_text("Always use TS.\n" * 250)

    env = {**os.environ, "TEXTUAL_HEADLESS": "1"}
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["rune", "review", "--probe-startup-time", str(tmp_path)],
        capture_output=True, text=True, env=env, timeout=5,
    )
    t1 = time.perf_counter()

    assert proc.returncode == 0, f"probe failed: {proc.stderr}"
    assert "READY" in proc.stdout, f"no READY marker in stdout: {proc.stdout!r}"

    # Two ways to compute cold-start:
    # (a) Wall-clock from subprocess.run start to return (includes process teardown)
    # (b) Embedded epoch_ms marker minus process spawn time (we don't have spawn epoch)
    # Use (a) — it's an upper bound; tighter than the previous test which only checked sleep + ceiling.
    elapsed = t1 - t0
    print(f"\ncold start measured: {elapsed*1000:.0f}ms")
    assert elapsed < 0.800, f"cold start {elapsed*1000:.0f}ms exceeds 800ms budget"
