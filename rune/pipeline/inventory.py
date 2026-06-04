from pathlib import Path
from rune.adapters.base import Platform, detect_platform, InjectionAdapter
from rune.adapters.claude_code import ClaudeCodeAdapter
from rune.adapters.cursor import CursorAdapter
from rune.adapters.copilot import CopilotAdapter
from rune.adapters.gemini import GeminiAdapter
from rune.adapters.windsurf import WindsurfAdapter
from rune.adapters.opencode import OpenCodeAdapter
from rune.adapters.generic import GenericAdapter
from rune.models.source import InjectionSource

# Ordered: specific adapters first, generic last as fallback
_ADAPTERS: list[tuple[Platform, InjectionAdapter]] = [
    (Platform.CLAUDE_CODE, ClaudeCodeAdapter()),
    (Platform.CURSOR, CursorAdapter()),
    (Platform.COPILOT, CopilotAdapter()),
    (Platform.GEMINI, GeminiAdapter()),
    (Platform.WINDSURF, WindsurfAdapter()),
    (Platform.OPENCODE, OpenCodeAdapter()),
    (Platform.GENERIC, GenericAdapter()),
]


def run_inventory(path: Path) -> tuple[list[InjectionSource], Platform]:
    """Run all matching adapters and return deduplicated sources + primary platform."""
    if not path.exists():
        return [], Platform.GENERIC

    seen: set[Path] = set()
    sources: list[InjectionSource] = []
    primary = Platform.GENERIC

    for platform, adapter in _ADAPTERS:
        if not adapter.detect(path):
            continue
        if primary == Platform.GENERIC and platform != Platform.GENERIC:
            primary = platform
        try:
            for source in adapter.list_sources(path):
                if source.path not in seen:
                    seen.add(source.path)
                    sources.append(source)
        except Exception:
            pass

    return sources, primary
