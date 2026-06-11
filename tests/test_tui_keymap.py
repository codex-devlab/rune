import pytest


@pytest.mark.asyncio
async def test_tui_quit_key():
    from rune.review.tui import ReviewApp
    app = ReviewApp(findings=[])
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app.is_running is False


@pytest.mark.asyncio
async def test_tui_space_toggles_selection():
    from rune.review.tui import ReviewApp
    findings = [{"id": 1}, {"id": 2}, {"id": 3}]
    app = ReviewApp(findings=findings)
    async with app.run_test() as pilot:
        await pilot.press("space")
        assert 0 in app.selected
        await pilot.press("j")
        await pilot.press("space")
        assert 1 in app.selected
        await pilot.press("c")
        assert app.selected == set()
        await pilot.press("q")
