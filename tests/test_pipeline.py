from pathlib import Path
from rune.pipeline.inventory import run_inventory
from rune.adapters.base import Platform


def test_inventory_empty_project(empty_project):
    sources, platform = run_inventory(empty_project)
    assert sources == []
    assert platform == Platform.GENERIC


def test_inventory_minimal_project(minimal_project):
    sources, platform = run_inventory(minimal_project)
    assert platform == Platform.CLAUDE_CODE
    assert len(sources) >= 1


def test_inventory_complex_project(complex_project):
    sources, platform = run_inventory(complex_project)
    assert platform == Platform.CLAUDE_CODE
    assert len(sources) >= 6  # CLAUDE.md + 6 rules


def test_inventory_never_raises(tmp_path):
    sources, platform = run_inventory(tmp_path / "does_not_exist")
    assert isinstance(sources, list)
