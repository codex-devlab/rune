from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks


class WindsurfAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".windsurfrules").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        rules = path / ".windsurfrules"
        if rules.exists():
            sources.append(self._read(rules, "windsurf_rules"))

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
