from pathlib import Path
from rune.adapters.base import Platform, detect_platform, InjectionAdapter
from rune.adapters.claude_code import ClaudeCodeAdapter
from rune.adapters.cursor import CursorAdapter
from rune.adapters.generic import GenericAdapter
from rune.models.source import InjectionSource

_ADAPTER_MAP: dict[Platform, InjectionAdapter] = {
    Platform.CLAUDE_CODE: ClaudeCodeAdapter(),
    Platform.CURSOR: CursorAdapter(),
    Platform.GENERIC: GenericAdapter(),
}


def run_inventory(path: Path) -> tuple[list[InjectionSource], Platform]:
    """Detect platform and list all injection sources. Never raises."""
    if not path.exists():
        return [], Platform.GENERIC

    platform = detect_platform(path)
    adapter = _ADAPTER_MAP.get(platform, _ADAPTER_MAP[Platform.GENERIC])

    try:
        sources = adapter.list_sources(path)
    except Exception:
        sources = []

    return sources, platform
