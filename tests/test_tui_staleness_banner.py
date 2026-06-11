import pytest
import asyncio
from pathlib import Path

@pytest.mark.asyncio
async def test_staleness_banner_on_mtime_change(tmp_path):
    from rune.review.tui import ReviewApp
    target = tmp_path / "rule.md"
    target.write_text("Always use TS.\n")
    findings = [{"path": str(target), "mtime_at_scan": target.stat().st_mtime}]
    app = ReviewApp(findings=findings, watch_files=True)
    async with app.run_test() as pilot:
        # Modify file to bump mtime
        await asyncio.sleep(0.05)
        target.write_text("Never use TS.\n")
        # Force mtime change (some filesystems have 1s resolution)
        import os, time
        t = target.stat().st_mtime + 2
        os.utime(target, (t, t))
        for _ in range(15):
            await asyncio.sleep(0.1)
            if app.stale_banner_visible:
                break
        assert app.stale_banner_visible is True
        await pilot.press("q")
