import json as jsonlib
from pathlib import Path
import typer
from rune.review.loader import load_chunk_refs
from rune.review.conflict_lexical import find_lexical_conflicts
from rune.review.dead_static import find_dead_rules_static
from rune.review.types import ReviewReport

# allow_interspersed_args: positional path 와 옵션의 순서를 자유롭게 허용.
# (예: `rune review . --json` 과 `rune review --json .` 둘 다 동작)
review_app = typer.Typer(
    help="Review rules for conflicts and dead rules",
    context_settings={"allow_interspersed_args": True},
)

# --apply 자동 삭제 게이트 임계값.
# 근거: 모달 기반(always vs never 등) 충돌은 confidence=0.95 로 정탐 신뢰도가 높다.
# 반면 모달 없는 어휘 휴리스틱(같은 verb + 상충 object, 예: use spaces vs use tabs)은
# confidence=0.6 으로 오탐 가능성이 있어, 잘못 자동 삭제하면 유효 규칙(c.b)이 사라진다.
# 따라서 0.95 정탐만 통과시키고 0.6 미만(0.6 포함)은 자동 삭제에서 제외한다.
# 임계값 0.9 는 0.95(통과)와 0.6(차단) 사이에서 모달 기반 정탐만 허용하도록 설정.
APPLY_CONFLICT_CONFIDENCE_THRESHOLD = 0.9


@review_app.callback(invoke_without_command=True)
def main(
    json: bool = typer.Option(False, "--json", help="Emit JSON to stdout. When combined with --apply, stdout emits the same JSON as operation_log.json."),
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
    confirm_delete_heuristics: bool = typer.Option(False, "--confirm-delete-heuristics", help="Acknowledge headless heuristic deletion; required for --apply --yes without --from-report or --select."),
    from_report: Path = typer.Option(None, "--from-report", help="Load ops from a JSON report file produced by --json."),
    select: str = typer.Option(None, "--select", help="Comma-separated finding IDs to apply (v0.3+; currently equivalent to --confirm-delete-heuristics)."),
    probe_startup_time: bool = typer.Option(False, "--probe-startup-time", hidden=True),
):
    import sys
    backup_root = path / ".rune" / "backups"

    # I6: --apply and --restore are mutually exclusive
    if apply and restore:
        print("error: --apply and --restore are mutually exclusive", file=sys.stderr)
        raise typer.Exit(2)

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
        from rune.review.conflict_nli import (
            find_nli_conflicts,
            build_l2_candidates,
            DEFAULT_MODEL,
            SMALL_MODEL,
        )
        model = SMALL_MODEL if nli_small else DEFAULT_MODEL
        # 후보군은 L1 결과가 아니라 전체 청크 쌍에 대한 경량 사전필터로 생성한다.
        # 이렇게 하면 L1 이 0건이어도 L2 가 새 의미 충돌을 찾을 수 있다.
        candidates = build_l2_candidates(refs)
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

        # C4: gate --apply --yes behind explicit confirmation
        import os
        allow_blind = os.environ.get("RUNE_ALLOW_BLIND_APPLY") == "1"
        has_explicit_confirm = (
            confirm_delete_heuristics or
            from_report is not None or
            select is not None or
            allow_blind
        )
        if not has_explicit_confirm:
            print(
                "error: --apply --yes requires explicit confirmation:\n"
                "  --confirm-delete-heuristics    (acknowledge headless heuristic deletion)\n"
                "  --from-report PATH             (apply ops from JSON report)\n"
                "  --select IDS                   (apply specific finding IDs — v0.3+)\n"
                "  RUNE_ALLOW_BLIND_APPLY=1       (legacy automation escape)\n"
                "Refusing to delete content based on heuristics alone.",
                file=sys.stderr,
            )
            raise typer.Exit(2)

        from rune.review.applier import apply_operations, prune_backups, Operation
        ops: list = []
        # per-finding confidence 게이트: HIGH-confidence(모달 기반) 충돌만 자동 삭제.
        # 저신뢰(휴리스틱) 충돌은 오탐 시 유효 규칙(c.b)을 삭제할 위험이 있어 제외하고
        # report-only 로 남긴다. --select 미구현이므로 저신뢰는 일괄 승인으로도 삭제 금지.
        low_confidence_skipped = 0
        for c in conflicts:
            if c.confidence >= APPLY_CONFLICT_CONFIDENCE_THRESHOLD:
                ops.append(Operation(kind="delete", ref=c.b))
            else:
                low_confidence_skipped += 1
        # dead_candidates 는 정적 trigger 기반이라 비교적 안전하나, 과삭제 방지를 위해
        # 충돌 게이트와 일관된 보수성을 유지한다(현재 static/events 단계 모두 자동 삭제 후보).
        for d in dead:
            ops.append(Operation(kind="delete", ref=d.chunk))
        if low_confidence_skipped:
            print(
                f"저신뢰 충돌 {low_confidence_skipped}건은 안전상 자동 삭제에서 제외됨 "
                f"(confidence < {APPLY_CONFLICT_CONFIDENCE_THRESHOLD}; report-only).",
                file=sys.stderr,
            )
        backup_root.mkdir(parents=True, exist_ok=True)
        log = apply_operations(ops, backup_dir=backup_root, base_root=path)
        if not no_prune:
            prune_backups(backup_root, keep=keep_backups)

        # I7: JSON identity contract — stdout JSON is byte-identical to operation_log.json on disk
        if json:
            print(jsonlib.dumps(log, indent=2))
        else:
            print(f"applied {len(log['ops'])} ops; backup {log['timestamp']}")
        return
    if json:
        print(jsonlib.dumps(report.to_dict(), indent=2))
        return
    # Default: launch TUI
    if probe_startup_time:
        import time as _time
        import sys as _sys
        _sys.stdout.write(f"READY {_time.time()}\n")
        _sys.stdout.flush()
        return  # exit immediately after marker for the probe
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

    # textual 미설치 시 TUI 대신 텍스트 리포트로 graceful fallback (크래시 금지).
    try:
        from rune.review.tui import ReviewApp
    except ImportError:
        _print_text_report(conflicts, dead)
        return
    app = ReviewApp(findings=findings, watch_files=True)
    app.run()


def _print_text_report(conflicts: list, dead: list) -> None:
    """TUI 를 못 쓸 때(textual 미설치) 콘솔에 충돌/데드 후보 목록을 출력한다."""
    print(f"충돌(conflicts): {len(conflicts)}건")
    for c in conflicts:
        print(
            f"  - [{c.source}] {c.a.path}:{c.a.start_line} <-> "
            f"{c.b.path}:{c.b.start_line}  ({c.reason}, confidence={c.confidence:.2f})"
        )
    print(f"데드 후보(dead candidates): {len(dead)}건")
    for d in dead:
        print(f"  - [{d.stage}] {d.chunk.path}:{d.chunk.start_line}  ({d.reason})")
    print()
    print("TUI를 쓰려면 pip install textual (또는 pip install 'rune[tui]')")
