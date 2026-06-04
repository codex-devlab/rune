import json
import time
from datetime import datetime, timezone
from pathlib import Path
import typer
from rich.console import Console

console = Console()


def append_event(events_file: Path, event: dict) -> None:
    """Append a single event to events.jsonl."""
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _collect_event(project_path: Path) -> dict:
    """Collect a single session snapshot."""
    from rune.pipeline.inventory import run_inventory
    sources, _ = run_inventory(project_path)
    return {
        "sources_loaded": [str(s.path) for s in sources],
        "trigger_matched": None,
        "token_total": sum(s.token_count for s in sources),
    }


def watch_cmd(
    path: Path = typer.Argument(default=None),
    interval: int = typer.Option(60, "--interval", help="Seconds between snapshots"),
    output: Path = typer.Option(None, "--output", help="Output file (default: events.jsonl)"),
):
    """Monitor session token usage and write events.jsonl."""
    target = path or Path.cwd()
    events_file = output or target / "events.jsonl"
    console.print(f"[cyan]Watching[/cyan] {target} → {events_file} (Ctrl+C to stop)")

    session_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    try:
        while True:
            event = _collect_event(target)
            event["session_id"] = session_id
            append_event(events_file, event)
            console.print(f"  [dim]{event['ts']}[/dim] tokens={event.get('token_total', 0)}")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/yellow]")
