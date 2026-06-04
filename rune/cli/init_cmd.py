from pathlib import Path
import typer
from rich.console import Console
from rune.scaffold.generator import scaffold_project

console = Console()


def init_cmd(
    path: Path = typer.Argument(default=None, help="Project directory"),
):
    """Initialize a new rune-optimized project structure."""
    target = path or Path.cwd()
    success = scaffold_project(target, "claude-code-base")
    if success:
        console.print(f"[green]초기화 완료[/green] — {target}")
        console.print("다음 단계: [bold]rune watch[/bold] 로 세션 데이터 수집 시작")
    else:
        console.print("[red]초기화 실패[/red]")
