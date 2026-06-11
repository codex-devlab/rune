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
    else:
        print(f"conflicts: {len(conflicts)}, dead candidates: {len(dead)}")
        print("(use --json for full report; TUI in Phase 2)")
