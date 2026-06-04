from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks

_SKIP_DIRS = {".git", ".repo", "node_modules", "__pycache__", ".venv", "venv"}
_AGENT_MD_NAMES = {"CLAUDE.md", "AGENTS.md", "GEMINI.md", "COPILOT.md"}


class GenericAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return True  # always available as fallback

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []
        for md_file in self._walk_md(path):
            text = self._safe_read(md_file)
            chunks = split_into_chunks(text)
            sources.append(
                InjectionSource(
                    path=md_file,
                    source_type="generic_md",
                    trigger=None,
                    chunks=chunks,
                )
            )
        return sources

    def _walk_md(self, path: Path):
        for item in path.rglob("*.md"):
            if any(skip in item.parts for skip in _SKIP_DIRS):
                continue
            if item.name in _AGENT_MD_NAMES:
                yield item

    def _safe_read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
