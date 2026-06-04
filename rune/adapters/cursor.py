from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks


class CursorAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".cursor").exists() or (path / ".cursorrules").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        rules_file = path / ".cursorrules"
        if rules_file.exists():
            sources.append(self._read(rules_file, "cursor_rules"))

        cursor_dir = path / ".cursor" / "rules"
        if cursor_dir.exists():
            for f in sorted(cursor_dir.glob("**/*.md")):
                sources.append(self._read(f, "cursor_rule"))

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
