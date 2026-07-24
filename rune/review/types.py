import hashlib
from dataclasses import dataclass, field
from pathlib import Path


def _short_hash(*parts: str) -> str:
    """sha256 의 앞 12자리를 반환한다. finding id 생성용 (충돌 확률 감소)."""
    raw = "\x00".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


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
    # loser(b) 청크 내 충돌 유발 라인 레인지(1-based inclusive).
    # 특정 불가 또는 전체 청크 삭제가 적절한 경우 None.
    b_lines: "tuple[int, int] | None" = None

    @property
    def id(self) -> str:
        """내용 기반 안정 식별자. c-<sha256(a.sha+b.sha+reason)[:8]>."""
        return "c-" + _short_hash(self.a.sha256, self.b.sha256, self.reason)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "reason": self.reason,
            "confidence": self.confidence,
            "source": self.source,
        }
        # additive: b_lines 가 None 이 아닐 때만 포함(구버전 리포트와 호환).
        if self.b_lines is not None:
            d["b_lines"] = list(self.b_lines)
        return d


@dataclass
class DeadCandidate:
    chunk: ChunkRef
    reason: str
    stage: str  # "static" | "events"

    @property
    def id(self) -> str:
        """내용 기반 안정 식별자. d-<sha256(chunk.sha+reason)[:8]>."""
        return "d-" + _short_hash(self.chunk.sha256, self.reason)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
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
