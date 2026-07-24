import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from rune.pipeline.inventory import run_inventory
from rune.pipeline.scorer import score_chunks_structural, score_chunks_tfidf
from rune.pipeline.dedup import find_dedup_pairs, find_dedup_chunk_pairs, find_dedup_rule_pairs
from rune.pipeline.trigger import extract_triggers
from rune.cli.optimize import has_optimization_targets, recommended_optimize_command
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

    # Dedup — 파일단위 비교는 유지하되, 청크(규칙) 단위 비교를 주(主) 신호로 쓴다.
    pairs = [] if no_semantic else find_dedup_pairs(sources)
    chunk_pairs = [] if no_semantic else find_dedup_chunk_pairs(sources)
    rule_pairs = [] if no_semantic else find_dedup_rule_pairs(sources)
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]
    high_chunk_pairs = [p for p in chunk_pairs if p.confidence == "HIGH"]
    high_rule_pairs = [p for p in rule_pairs if p.confidence == "HIGH"]

    # Trigger
    trigger_results = extract_triggers(sources)

    total_tokens = sum(s.token_count for s in sources)
    level = _determine_level(sources)

    # optimize 가 실제로 처리할 대상이 있을 때만 추천한다(추천-결과 정합).
    # 규칙 단위 중복(rule_pairs) 은 optimize --level 3 이 처리한다.
    # has_optimization_targets 는 chunk_pairs 기반이므로 rule_pairs 는 별도 신호.
    recommend_optimize = has_optimization_targets(sources) or bool(high_rule_pairs)
    # 신호 종류에 맞춰 실제 절약을 내는 정확한 명령을 안내한다.
    optimize_command = recommended_optimize_command(sources)
    # 규칙 단위 중복만 있고 청크 단위 중복이 없으면 level 3 을 직접 안내
    if not optimize_command and high_rule_pairs:
        optimize_command = "rune optimize --level 3 --dry-run"

    report = AnalysisReport(
        total_tokens=total_tokens,
        sources=sources,
        dedup_pairs=pairs,
        trigger_results=trigger_results,
        level=level,
    )

    if output_json:
        typer.echo(json.dumps({
            "schema_version": "1.1",
            "total_tokens": report.total_tokens,
            "level": report.level,
            "platform": platform.value,
            "source_count": len(sources),
            "dedup_high": len(high_pairs),
            "dedup_chunk_high": len(high_chunk_pairs),
            "dedup_rule_high": len(high_rule_pairs),
            "recommend_optimize": recommend_optimize,
            "optimize_command": optimize_command,
            "sources": [
                {"path": str(s.path), "type": s.source_type, "tokens": s.token_count}
                for s in sources
            ],
        }))
        return

    _render_report(report, platform.value, target, high_chunk_pairs, high_rule_pairs, recommend_optimize, optimize_command)


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


def _render_report(
    report: AnalysisReport,
    platform: str,
    target: Path,
    high_chunk_pairs: list | None = None,
    high_rule_pairs: list | None = None,
    recommend_optimize: bool = False,
    optimize_command: str | None = None,
) -> None:
    high_chunk_pairs = high_chunk_pairs or []
    high_rule_pairs = high_rule_pairs or []
    console.print(f"\n[bold]rune analyze[/bold] — {target}")
    console.print(f"Platform: [cyan]{platform}[/cyan]\n")

    table = Table(title="주입 소스")
    table.add_column("파일", style="dim")
    table.add_column("타입")
    table.add_column("토큰", justify="right")

    for s in report.sources:
        try:
            rel = s.path.relative_to(target)
        except ValueError:
            rel = s.path
        table.add_row(str(rel), s.source_type, str(s.token_count))

    console.print(table)
    console.print(f"\n[bold]총 토큰[/bold]: {report.total_tokens:,}")

    high_pairs = [p for p in report.dedup_pairs if p.confidence == "HIGH"]
    if high_pairs:
        console.print(f"[red]파일 단위 중복[/red]: {len(high_pairs)}쌍 (HIGH confidence)")
        for p in high_pairs[:10]:
            try:
                a = p.source_a.relative_to(target)
                b = p.source_b.relative_to(target)
            except ValueError:
                a, b = p.source_a, p.source_b
            console.print(f"  - {a} ↔ {b} ({p.similarity:.2%})")
        if len(high_pairs) > 10:
            console.print(f"  ... 외 {len(high_pairs) - 10}쌍")

    # 청크(문단) 단위 중복 — 파일이 통째로 같지 않아도 같은 문단이 여러 곳에
    # 들어있으면 여기서 보고한다(주 신호).
    if high_chunk_pairs:
        console.print(f"[red]문단 단위 중복[/red]: {len(high_chunk_pairs)}쌍 (HIGH confidence)")
        for p in high_chunk_pairs[:10]:
            try:
                a = p.source_a.relative_to(target)
                b = p.source_b.relative_to(target)
            except ValueError:
                a, b = p.source_a, p.source_b
            preview = p.text_a.strip().splitlines()[0][:48] if p.text_a.strip() else ""
            console.print(f"  - \"{preview}\": {a} ↔ {b} ({p.similarity:.2%})")
        if len(high_chunk_pairs) > 10:
            console.print(f"  ... 외 {len(high_chunk_pairs) - 10}쌍")

    # 서브청크(규칙 라인) 단위 중복 — 문단이 달라도 동일 규칙이 여러 파일에
    # 섞여 있으면 여기서 보고한다(서브청크 신호).
    if high_rule_pairs:
        console.print(f"[red]규칙 단위 중복[/red]: {len(high_rule_pairs)}쌍 (HIGH confidence)")
        for p in high_rule_pairs[:10]:
            try:
                a = p.source_a.relative_to(target)
                b = p.source_b.relative_to(target)
            except ValueError:
                a, b = p.source_a, p.source_b
            preview = p.text.strip()[:48] if p.text.strip() else ""
            console.print(f"  - \"{preview}\": {a}:{p.line_a} ↔ {b}:{p.line_b} ({p.similarity:.2%})")
        if len(high_rule_pairs) > 10:
            console.print(f"  ... 외 {len(high_rule_pairs) - 10}쌍")

    # 추천은 optimize 가 실제로 처리할 대상이 있을 때만(추천-결과 정합).
    # 신호 종류에 맞춰 실제 절약을 내는 정확한 명령을 안내한다.
    if recommend_optimize and optimize_command:
        console.print(f"\n추천: [bold]{optimize_command}[/bold] 으로 최적화 미리보기")
    else:
        console.print("\n[green]최적화 불필요[/green] — 중복이 없습니다.")
