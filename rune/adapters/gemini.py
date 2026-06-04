from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks


class GeminiAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / "GEMINI.md").exists() or (path / ".gemini").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        gemini_md = path / "GEMINI.md"
        if gemini_md.exists():
            sources.append(self._read(gemini_md, "gemini_md"))

        gemini_dir = path / ".gemini"
        if gemini_dir.exists():
            for f in sorted(gemini_dir.glob("**/*.md")):
                sources.append(self._read(f, "gemini_rule"))

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
