from pathlib import Path
import typer
from rich.console import Console
from rune.scaffold.generator import scaffold_project, available_types

console = Console()


def scaffold_cmd(
    template_type: str = typer.Option("claude-code-base", "--type", help="Template type"),
    path: Path = typer.Argument(default=None),
):
    """Generate project-type-specific rule templates."""
    target = path or Path.cwd()
    success = scaffold_project(target, template_type)
    if success:
        console.print(f"[green]스캐폴딩 완료[/green] ({template_type}) — {target}")
    else:
        console.print(f"[yellow]알 수 없는 타입:[/yellow] {template_type}")
        console.print(f"사용 가능: {', '.join(available_types())}")
