import shutil
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_AVAILABLE_TYPES = {"claude-code-base", "python-backend"}


def scaffold_project(project_path: Path, template_type: str) -> bool:
    """Copy template files into project_path. Returns True on success."""
    template_dir = _TEMPLATES_DIR / template_type
    if not template_dir.exists():
        return False

    project_path.mkdir(parents=True, exist_ok=True)
    for src in template_dir.rglob("*"):
        if src.is_file():
            rel = src.relative_to(template_dir)
            # skip old flat rules/ — only copy .claude/rules/ structure
            if str(rel).startswith("rules/"):
                continue
            dst = project_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return True


def available_types() -> list[str]:
    return sorted(_AVAILABLE_TYPES)
