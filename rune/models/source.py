from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    text: str
    start_line: int
    end_line: int
    token_count: int
    importance_score: float = 0.0


@dataclass
class InjectionSource:
    path: Path
    source_type: str  # "claude_md" | "rule" | "memory" | "skill"
    trigger: str | None
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        return sum(c.token_count for c in self.chunks)
