import pytest
from pathlib import Path


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Benchmark-0: completely empty directory."""
    return tmp_path


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """Benchmark-1: single CLAUDE.md, no rules."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\nBe concise. Write tests first.\n"
    )
    return tmp_path


@pytest.fixture
def complex_project(tmp_path: Path) -> Path:
    """Benchmark-2: CLAUDE.md + multiple rules (pmo-vault-like)."""
    (tmp_path / "CLAUDE.md").write_text("# PMO Vault\n\nCore rules apply.\n")
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    rule_texts = {
        "git.md": "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push main. Always write descriptive commit messages. Squash fixup commits before merging.",
        "python.md": "## Python Rules\n\nTrigger: python, pytest\n\nUse type hints always. Run mypy before committing. Prefer dataclasses over plain dicts for structured data.",
        "deploy.md": "## Deploy Rules\n\nTrigger: deploy, production\n\nRun tests before deploy. Tag releases with semver. Never deploy on Fridays.",
        "docs.md": "## Docs Rules\n\nTrigger: docs, readme\n\nKeep README updated. Add docstrings to all public functions. Update changelog on every release.",
        "security.md": "## Security Rules\n\nTrigger: auth, secret, password\n\nNever commit secrets. Use environment variables for credentials. Rotate tokens every 90 days.",
        "duplicate.md": "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push main. Always write descriptive commit messages. Squash fixup commits before merging.",
    }
    for name, content in rule_texts.items():
        (rules_dir / name).write_text(content)
    return tmp_path
