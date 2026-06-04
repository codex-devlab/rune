import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from rune.pipeline.inventory import run_inventory
from rune.pipeline.scorer import score_chunks_structural, score_chunks_tfidf
from rune.pipeline.dedup import find_dedup_pairs
from rune.pipeline.trigger import extract_triggers
from rune.models.report import AnalysisReport

console = Console()


def analyze_cmd(
    path: Path = typer.Argument(default=None, help="Project directory to analyze"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    no_semantic: bool = typer.Option(False, "--no-semantic", help="Skip sentence-transformers"),
):
    """Analyze static token injection in an LLM agent project."""
    target = path or Path.cwd()

    sources, platform = run_inventory(target)

    if not sources:
        if output_json:
            typer.echo(json.dumps({"total_tokens": 0, "sources": [], "level": 0}))
        else:
            console.print(f"[yellow]설정 없음[/yellow] — {target}")
            console.print("추천: [bold]rune init[/bold] 으로 시작하세요.")
        return

    # Score
    all_chunks = [c for s in sources for c in s.chunks]
    score_chunks_structural(all_chunks)
    score_chunks_tfidf(all_chunks)

    # Dedup
    pairs = [] if no_semantic else find_dedup_pairs(sources)
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]

    # Trigger
    trigger_results = extract_triggers(sources)

    total_tokens = sum(s.token_count for s in sources)
    level = _determine_level(sources)

    report = AnalysisReport(
        total_tokens=total_tokens,
        sources=sources,
        dedup_pairs=pairs,
        trigger_results=trigger_results,
        level=level,
    )

    if output_json:
        typer.echo(json.dumps({
            "total_tokens": report.total_tokens,
            "level": report.level,
            "platform": platform.value,
            "source_count": len(sources),
            "dedup_high": len(high_pairs),
            "sources": [
                {"path": str(s.path), "type": s.source_type, "tokens": s.token_count}
                for s in sources
            ],
        }))
        return

    _render_report(report, platform.value, target)


def _determine_level(sources) -> int:
    if not sources:
        return 0
    total = sum(s.token_count for s in sources)
    count = len(sources)
    if count >= 5 or total >= 500:
        return 3
    if count >= 3 or total >= 200:
        return 2
    return 1


def _render_report(report: AnalysisReport, platform: str, target: Path) -> None:
    console.print(f"\n[bold]rune analyze[/bold] — {target}")
    console.print(f"Platform: [cyan]{platform}[/cyan]\n")

    table = Table(title="주입 소스")
    table.add_column("파일", style="dim")
    table.add_column("타입")
    table.add_column("토큰", justify="right")

    for s in report.sources:
        table.add_row(str(s.path.name), s.source_type, str(s.token_count))

    console.print(table)
    console.print(f"\n[bold]총 토큰[/bold]: {report.total_tokens:,}")

    high_pairs = [p for p in report.dedup_pairs if p.confidence == "HIGH"]
    if high_pairs:
        console.print(f"[red]중복 탐지[/red]: {len(high_pairs)}쌍 (HIGH confidence)")
        for p in high_pairs:
            console.print(f"  - {p.source_a.name} ↔ {p.source_b.name} ({p.similarity:.2%})")

    if report.level <= 1:
        console.print("\n[green]최적화 불필요[/green] — 설정이 적정합니다.")
    else:
        console.print("\n추천: [bold]rune optimize --dry-run[/bold] 으로 최적화 미리보기")
