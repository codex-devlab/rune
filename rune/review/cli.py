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
    l2: bool = typer.Option(False, "--l2"),
    allow_model_download: bool = typer.Option(False, "--allow-model-download"),
    nli_small: bool = typer.Option(False, "--nli-small"),
    events_path: Path = typer.Option(None, "--events-path"),
    events_window_days: int = typer.Option(30, "--events-window-days"),
    apply: bool = typer.Option(False, "--apply"),
    yes: bool = typer.Option(False, "--yes"),
    restore: str = typer.Option(None, "--restore"),
    keep_backups: int = typer.Option(10, "--keep-backups"),
    no_prune: bool = typer.Option(False, "--no-prune"),
):
    import sys
    backup_root = path / ".rune" / "backups"
    if restore:
        snap = backup_root / restore
        if not snap.exists():
            print(f"snapshot not found: {restore}", file=sys.stderr)
            raise typer.Exit(2)
        for f in snap.iterdir():
            if f.name == "operation_log.json":
                continue
            target = path / f.name
            target.write_bytes(f.read_bytes())
        print(f"restored from {restore}")
        return

    refs_with_triggers = load_chunk_refs(path)
    refs = [r for r, _ in refs_with_triggers]
    conflicts = find_lexical_conflicts(refs)
    dead = find_dead_rules_static(refs, repo_root=path)

    if events_path is not None:
        from rune.review.dead_events import find_dead_rules_events
        events_dead = find_dead_rules_events(refs, events_path=events_path, window_days=events_window_days)
        # Merge: add Stage B candidates to existing dead list
        dead = dead + events_dead

    if l2:
        from rune.review.conflict_nli import find_nli_conflicts, DEFAULT_MODEL, SMALL_MODEL
        model = SMALL_MODEL if nli_small else DEFAULT_MODEL
        # Candidate pairs = chunk pairs that L1 already identified (lexically adjacent)
        # For v0.2 we re-use the L1 conflict ref pairs as the candidate set.
        candidates = [(c.a, c.b) for c in conflicts]
        nli_pairs = find_nli_conflicts(
            candidates, model_name=model, allow_download=allow_model_download
        )
        conflicts = conflicts + nli_pairs  # merge
        report_tier = "L2"
        report_schema = "1.1"
    else:
        report_tier = "L1"
        report_schema = "1.0"

    report = ReviewReport(
        schema_version=report_schema,
        detector_tier=report_tier,
        conflicts=conflicts,
        dead_candidates=dead,
    )
    if apply:
        if not yes:
            print("refusing to apply without --yes", file=sys.stderr)
            raise typer.Exit(2)
        from rune.review.applier import apply_operations, prune_backups, Operation
        ops: list = []
        for c in conflicts:
            ops.append(Operation(kind="delete", ref=c.b))
        for d in dead:
            ops.append(Operation(kind="delete", ref=d.chunk))
        backup_root.mkdir(parents=True, exist_ok=True)
        log = apply_operations(ops, backup_dir=backup_root)
        if not no_prune:
            prune_backups(backup_root, keep=keep_backups)
        print(f"applied {len(log['ops'])} ops; backup {log['timestamp']}")
        return
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
