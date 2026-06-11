from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks

_IGNORE_PARTS = {".rune", ".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORE_PARTS for part in path.parts)


class ClaudeCodeAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".claude").exists() or (path / "CLAUDE.md").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        # CLAUDE.md files (root and subdirectories)
        for md_file in sorted(path.glob("**/CLAUDE.md")):
            if _is_ignored(md_file.relative_to(path)):
                continue
            sources.append(self._read_source(md_file, "claude_md"))

        # .claude/rules/
        rules_dir = path / ".claude" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.glob("**/*.md")):
                if _is_ignored(rule_file.relative_to(path)):
                    continue
                sources.append(self._read_source(rule_file, "rule"))

        # .claude/skills/
        skills_dir = path / ".claude" / "skills"
        if skills_dir.exists():
            for skill_file in sorted(skills_dir.glob("**/SKILL.md")):
                if _is_ignored(skill_file.relative_to(path)):
                    continue
                sources.append(self._read_source(skill_file, "skill"))

        return sources

    def _read_source(self, path: Path, source_type: str) -> InjectionSource:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        # Symlinks are deduplicated to a canonical file; do not double-count tokens
        if path.is_symlink():
            chunks = []
        else:
            chunks = split_into_chunks(text)
        trigger = self._extract_trigger(text)
        return InjectionSource(
            path=path,
            source_type=source_type,
            trigger=trigger,
            chunks=chunks,
        )

    def _extract_trigger(self, text: str) -> str | None:
        """Extract first trigger keyword line if present."""
        for line in text.splitlines():
            lower = line.lower().strip()
            if lower.startswith("trigger:") or lower.startswith("트리거:"):
                return line.split(":", 1)[-1].strip()
        return None
