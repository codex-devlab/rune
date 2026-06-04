from pathlib import Path
from rune.adapters.base import InjectionAdapter
from rune.models.source import InjectionSource
from rune.pipeline.tokenizer import split_into_chunks


class CopilotAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (
            (path / ".github" / "copilot-instructions.md").exists()
            or (path / ".github" / "copilot").exists()
        )

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        instructions = path / ".github" / "copilot-instructions.md"
        if instructions.exists():
            sources.append(self._read(instructions, "copilot_instructions"))

        copilot_dir = path / ".github" / "copilot"
        if copilot_dir.exists():
            for f in sorted(copilot_dir.glob("**/*.md")):
                sources.append(self._read(f, "copilot_rule"))

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
