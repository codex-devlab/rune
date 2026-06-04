from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from rune.models.source import InjectionSource


class Platform(str, Enum):
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    COPILOT = "copilot"
    GENERIC = "generic"


def detect_platform(path: Path) -> Platform:
    if (path / ".claude").exists():
        return Platform.CLAUDE_CODE
    if (path / ".cursor").exists():
        return Platform.CURSOR
    if (path / ".github" / "copilot").exists():
        return Platform.COPILOT
    if any(path.glob("CLAUDE.md")):
        return Platform.CLAUDE_CODE
    if any(path.glob(".cursorrules")):
        return Platform.CURSOR
    return Platform.GENERIC


class InjectionAdapter(ABC):
    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this adapter handles the given project path."""

    @abstractmethod
    def list_sources(self, path: Path) -> list[InjectionSource]:
        """Return all injection sources. MUST return [] on missing files, never raise."""
