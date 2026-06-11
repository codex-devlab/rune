import pytest


@pytest.mark.asyncio
async def test_tui_quit_key():
    from rune.review.tui import ReviewApp
    app = ReviewApp(findings=[])
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app.is_running is False
