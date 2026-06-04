from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from rune.models.source import InjectionSource


class Platform(str, Enum):
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    COPILOT = "copilot"
    GEMINI = "gemini"
    WINDSURF = "windsurf"
    OPENCODE = "opencode"
    GENERIC = "generic"


def detect_platform(path: Path) -> Platform:
    """Return the primary platform. For multi-platform projects use run_inventory()."""
    if (path / ".claude").exists() or (path / "CLAUDE.md").exists():
        return Platform.CLAUDE_CODE
    if (path / ".cursor").exists() or (path / ".cursorrules").exists():
        return Platform.CURSOR
    if (path / ".github" / "copilot-instructions.md").exists() or (path / ".github" / "copilot").exists():
        return Platform.COPILOT
    if (path / "GEMINI.md").exists() or (path / ".gemini").exists():
        return Platform.GEMINI
    if (path / ".windsurfrules").exists():
        return Platform.WINDSURF
    if (path / ".opencode").exists():
        return Platform.OPENCODE
    return Platform.GENERIC


class InjectionAdapter(ABC):
    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this adapter handles the given project path."""

    @abstractmethod
    def list_sources(self, path: Path) -> list[InjectionSource]:
        """Return all injection sources. MUST return [] on missing files, never raise."""
