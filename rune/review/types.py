from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChunkRef:
    path: Path
    start_line: int
    end_line: int
    sha256: str
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "start_line": self.start_line,
            "end_line": self.end_line,
            "sha256": self.sha256,
        }


@dataclass
class ConflictPair:
    a: ChunkRef
    b: ChunkRef
    reason: str
    confidence: float
    source: str  # "lexical" | "nli"

    def to_dict(self) -> dict:
        return {
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class DeadCandidate:
    chunk: ChunkRef
    reason: str
    stage: str  # "static" | "events"

    def to_dict(self) -> dict:
        return {
            "chunk": self.chunk.to_dict(),
            "reason": self.reason,
            "stage": self.stage,
        }


@dataclass
class ReviewReport:
    schema_version: str = "1.0"
    conflicts: list[ConflictPair] = field(default_factory=list)
    dead_candidates: list[DeadCandidate] = field(default_factory=list)
    detector_tier: str = "L1"

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "detector_tier": self.detector_tier,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "dead_candidates": [d.to_dict() for d in self.dead_candidates],
        }
