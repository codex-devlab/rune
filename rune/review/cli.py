import json as jsonlib
from pathlib import Path
import typer
from rune.review.loader import load_chunk_refs
from rune.review.conflict_lexical import find_lexical_conflicts
from rune.review.dead_static import find_dead_rules_static
from rune.review.types import ReviewReport

review_app = typer.Typer(help="Review rules for conflicts and dead rules")


@review_app.callback(invoke_without_command=True)
def main(
    json: bool = typer.Option(False, "--json"),
    path: Path = typer.Argument(Path(".")),
):
    refs_with_triggers = load_chunk_refs(path)
    refs = [r for r, _ in refs_with_triggers]
    conflicts = find_lexical_conflicts(refs)
    dead = find_dead_rules_static(refs, repo_root=path)
    report = ReviewReport(
        schema_version="1.0",
        detector_tier="L1",
        conflicts=conflicts,
        dead_candidates=dead,
    )
    if json:
        print(jsonlib.dumps(report.to_dict(), indent=2))
        return
    # Default: launch TUI
    from rune.review.tui import ReviewApp
    findings = []
    for c in conflicts:
        d = c.to_dict()
        d["kind"] = "conflict"
        d["path"] = str(c.a.path)
        d["mtime_at_scan"] = c.a.path.stat().st_mtime if c.a.path.exists() else 0.0
        findings.append(d)
    for dc in dead:
        d = dc.to_dict()
        d["kind"] = "dead"
        d["path"] = str(dc.chunk.path)
        d["mtime_at_scan"] = dc.chunk.path.stat().st_mtime if dc.chunk.path.exists() else 0.0
        findings.append(d)
    app = ReviewApp(findings=findings, watch_files=True)
    app.run()
