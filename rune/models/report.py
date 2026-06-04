from dataclasses import dataclass, field
from pathlib import Path
from rune.models.source import InjectionSource


@dataclass
class DedupPair:
    source_a: Path
    source_b: Path
    similarity: float
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"


@dataclass
class TriggerResult:
    source: Path
    keywords: list[str]
    method: str  # "parsed" | "tfidf"


@dataclass
class AnalysisReport:
    total_tokens: int
    sources: list[InjectionSource]
    dedup_pairs: list[DedupPair]
    trigger_results: list[TriggerResult]
    level: int  # 0-3
    estimated_savings: int = 0
