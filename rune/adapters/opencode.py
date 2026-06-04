from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks


class OpenCodeAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".opencode").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        agents_dir = path / ".opencode" / "agents"
        if agents_dir.exists():
            for f in sorted(agents_dir.glob("**/*.md")):
                sources.append(self._read(f, "opencode_agent"))

        return sources

    def _read(self, path: Path, source_type: str) -> InjectionSource:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        return InjectionSource(
            path=path,
            source_type=source_type,
            trigger=None,
            chunks=split_into_chunks(text),
        )
