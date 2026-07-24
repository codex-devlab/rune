import json as jsonlib
import re
import sys
from pathlib import Path
import typer
from rune.review.loader import load_chunk_refs
from rune.review.conflict_lexical import find_lexical_conflicts
from rune.review.dead_static import find_dead_rules_static
from rune.review.types import ChunkRef, ConflictPair, DeadCandidate, ReviewReport

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

# 혼합 청크 판별 임계값 — 헤더/Trigger 제외 규칙 라인이 이 수 이상이면 혼합 청크.
# 근거: 단일 규칙은 통상 1줄 본문이므로 2줄 이상 = 복수 규칙 공존 가능성.
_MIXED_CHUNK_LINE_THRESHOLD = 2

# 혼합 청크 필터에서 제외할 줄 패턴 (마크다운 헤더, Trigger: 지시자).
_RE_HEADER = re.compile(r"^\s*#+")
_RE_TRIGGER = re.compile(r"^\s*Trigger\s*:", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 헬퍼: 청크 키 / 혼합 청크 판별 / protected 집합 / 리포트 파싱
# ---------------------------------------------------------------------------

def _chunk_key(ref: ChunkRef) -> tuple:
    """청크를 식별하는 불변 3-tuple (path, start_line, sha256).

    applier 의 sha256 스테일 검증과 동일한 식별 기준을 사용하므로
    '파일이 스캔 이후 변경되면 applier 가 거부' 라는 최종 안전망과 일관성이 유지된다.
    """
    return (str(ref.path), ref.start_line, ref.sha256)


def _resolve_chunk_text(ref: "ChunkRef") -> "str | None":
    """디스크에서 청크 본문을 읽어 반환한다.

    --from-report 경로에서 ChunkRef.text 가 비어 있을 때 혼합 청크 판별을 위해 호출된다.
    파일 미존재·읽기 실패·라인 범위 이탈 시 None 을 반환한다.

    None 반환 시 호출자는 보수적으로 삭제를 차단(protected_skipped 처리)해야 한다.
    확인 불가한 청크를 지우지 않는 것이 안전 원칙이다.
    """
    try:
        lines = Path(ref.path).read_text(encoding="utf-8").splitlines()
        # start_line / end_line 은 1-based; 슬라이싱은 0-based.
        start_idx = ref.start_line - 1
        end_idx = ref.end_line  # end_line 포함이므로 슬라이싱 상한은 end_line (=end_line-1+1)
        if start_idx < 0 or end_idx > len(lines):
            return None
        return "\n".join(lines[start_idx:end_idx])
    except Exception:
        return None


def _is_mixed_chunk(text: str) -> bool:
    """청크가 단독 규칙이 아닌 여러 규칙을 포함하는지(혼합 여부) 판별.

    마크다운 헤더(#…)와 'Trigger:' 줄을 제외한 비어있지 않은 줄이
    _MIXED_CHUNK_LINE_THRESHOLD(2) 개 이상이면 혼합 청크로 간주한다.
    혼합 청크를 통째로 자동 삭제하면 충돌/데드와 무관한 유효 규칙까지 소실된다.
    """
    rule_lines = [
        ln for ln in text.splitlines()
        if ln.strip()
        and not _RE_HEADER.match(ln)
        and not _RE_TRIGGER.match(ln)
    ]
    return len(rule_lines) >= _MIXED_CHUNK_LINE_THRESHOLD


def _build_protected_keys(conflicts: list) -> set:
    """confidence < APPLY_CONFLICT_CONFIDENCE_THRESHOLD 인 충돌의 loser(c.b) 청크 키 집합.

    이 집합에 속한 청크는 고신뢰 충돌에 의한 동반 삭제를 방지한다.
    예: 0.95 충돌 loser 와 0.6 충돌 loser 가 같은 청크이면, 0.95 삭제 op 를 만들더라도
    protected 검사에서 제외시켜 report-only 로 강등한다.
    """
    return {
        _chunk_key(c.b)
        for c in conflicts
        if c.confidence < APPLY_CONFLICT_CONFIDENCE_THRESHOLD
    }


def _load_report_from_json(report_path: Path) -> ReviewReport:
    """JSON 리포트 파일(review --json 스키마)을 파싱하여 ReviewReport 객체로 반환.

    --from-report 지정 시 라이브 스캔 결과를 사용하지 않고 이 결과만으로 ops 를 구성한다.
    파일 미존재·파싱 불가 시 ValueError/OSError 를 발생시키고, 호출자가 exit 2 처리한다.
    """
    raw = jsonlib.loads(report_path.read_text(encoding="utf-8"))

    conflicts: list[ConflictPair] = []
    for c in raw.get("conflicts", []):
        a = ChunkRef(
            path=Path(c["a"]["path"]),
            start_line=c["a"]["start_line"],
            end_line=c["a"]["end_line"],
            sha256=c["a"]["sha256"],
        )
        b = ChunkRef(
            path=Path(c["b"]["path"]),
            start_line=c["b"]["start_line"],
            end_line=c["b"]["end_line"],
            sha256=c["b"]["sha256"],
        )
        # b_lines: 구버전 리포트엔 없으므로 없으면 None(additive 스키마).
        raw_bl = c.get("b_lines")
        b_lines = tuple(raw_bl) if raw_bl and len(raw_bl) == 2 else None
        conflicts.append(ConflictPair(
            a=a, b=b,
            reason=c.get("reason", ""),
            confidence=float(c.get("confidence", 0.0)),
            source=c.get("source", ""),
            b_lines=b_lines,
        ))

    dead: list[DeadCandidate] = []
    for d in raw.get("dead_candidates", []):
        chunk_data = d["chunk"]
        chunk = ChunkRef(
            path=Path(chunk_data["path"]),
            start_line=chunk_data["start_line"],
            end_line=chunk_data["end_line"],
            sha256=chunk_data["sha256"],
        )
        dead.append(DeadCandidate(
            chunk=chunk,
            reason=d.get("reason", ""),
            stage=d.get("stage", "static"),
        ))

    return ReviewReport(
        schema_version=raw.get("schema_version", "1.0"),
        detector_tier=raw.get("detector_tier", "L1"),
        conflicts=conflicts,
        dead_candidates=dead,
    )


# ---------------------------------------------------------------------------
# apply ops 구성 — 게이트·순수성·정적 dead 필터를 한 곳에서 처리
# ---------------------------------------------------------------------------

def _build_apply_ops(conflicts: list, dead: list) -> tuple:
    """충돌/데드 후보로부터 apply op 목록과 제외 통계를 반환.

    반환: (ops, low_confidence_skipped, protected_skipped, static_dead_skipped,
           line_precision_applied)

    적용 규칙 (우선순위 순):
    1. confidence < APPLY_CONFLICT_CONFIDENCE_THRESHOLD 충돌 → low_confidence_skipped.
    2. loser(c.b) 청크가 protected 집합(저신뢰 loser 와 동일 청크) → protected_skipped.
    3. loser(c.b) 청크가 혼합 청크(_is_mixed_chunk):
       - b_lines 있음 → Operation(kind="delete_lines") 생성 (라인 정밀 삭제).
       - b_lines 없음 → 기존 보수적 제외(protected_skipped).
    4. dead stage=="static" → static_dead_skipped (오탐 빈도가 높아 자동 삭제 금지).
    5. dead stage=="events" (사용 이벤트 확증) → delete op 허용.
    """
    from rune.review.applier import Operation

    # 저신뢰 loser 청크 키 집합 — 동반 삭제 차단을 위한 보호 집합.
    protected_keys = _build_protected_keys(conflicts)

    ops: list = []
    low_confidence_skipped = 0
    protected_skipped = 0
    line_precision_applied = 0  # 혼합 청크에 라인 정밀 삭제가 적용된 건수

    for c in conflicts:
        if c.confidence < APPLY_CONFLICT_CONFIDENCE_THRESHOLD:
            # 저신뢰 충돌: loser 삭제 금지 (오탐 시 유효 규칙 소실 위험).
            low_confidence_skipped += 1
            continue
        key = _chunk_key(c.b)
        if key in protected_keys:
            # 고신뢰 충돌이더라도 loser 가 저신뢰 충돌의 loser 와 같은 청크이면
            # 동반 삭제를 차단하고 report-only 로 강등한다.
            protected_skipped += 1
            continue
        # 혼합 청크 검사: text 가 비어 있으면(--from-report 경로) 디스크에서 직접 해석.
        chunk_text = c.b.text if c.b.text else _resolve_chunk_text(c.b)
        if chunk_text is None:
            # 본문을 해석할 수 없으면 보수적으로 삭제에서 제외.
            # 확인 불가한 청크를 지우지 않는 것이 안전 원칙이다.
            protected_skipped += 1
            continue
        if _is_mixed_chunk(chunk_text):
            # 혼합 청크: 통째 삭제 시 관련 없는 규칙까지 소실된다.
            # b_lines(충돌 유발 라인)가 있으면 라인 정밀 삭제로 근본 해결.
            # b_lines 없으면(구버전 리포트 등) 기존 보수적 제외 유지.
            b_lines = getattr(c, "b_lines", None)
            if b_lines is not None:
                ops.append(Operation(kind="delete_lines", ref=c.b, line_range=b_lines))
                line_precision_applied += 1
            else:
                protected_skipped += 1
            continue
        ops.append(Operation(kind="delete", ref=c.b))

    static_dead_skipped = 0
    for d in dead:
        if d.stage == "static":
            # 정적 휴리스틱(트리거 키워드 단독 판단)은 오탐이 잦아 자동 삭제 금지.
            # stage=="events" (실사용 이벤트 확증) 만 삭제 허용.
            static_dead_skipped += 1
            continue
        # stage=="events" — 사용 이벤트로 확증된 데드 규칙만 삭제.
        # 단, 혼합 청크 또는 본문 해석 불가이면 conflict 경로와 동일하게 보수적으로 제외.
        # dead 도 청크 단위 삭제이므로 혼합 청크 게이트를 일관 적용하는 것이 안전하다.
        dead_text = d.chunk.text if d.chunk.text else _resolve_chunk_text(d.chunk)
        if dead_text is None:
            # 본문 해석 불가(파일 미존재 등) → 보수적으로 제외.
            # 확인 불가한 청크를 지우지 않는 것이 안전 원칙이다.
            protected_skipped += 1
            continue
        if _is_mixed_chunk(dead_text):
            # 혼합 청크: 관련 없는 규칙까지 소실될 수 있어 제외.
            protected_skipped += 1
            continue
        ops.append(Operation(kind="delete", ref=d.chunk))

    return ops, low_confidence_skipped, protected_skipped, static_dead_skipped, line_precision_applied


def _build_select_ops(
    conflicts: list,
    dead: list,
    select_ids: frozenset,
) -> tuple:
    """--select 경로 전용 op 구성. confidence 게이트를 면제하고 id 집합으로 필터링.

    반환: (ops, protected_skipped, line_precision_applied, unknown_ids)
      - ops: 실행 대상 Operation 목록.
      - protected_skipped: 혼합 청크 + b_lines 없는 경우처럼 안전상 제외된 건수.
      - line_precision_applied: 혼합 청크에 라인 정밀 삭제가 적용된 건수.
      - unknown_ids: select_ids 에 있지만 실제 finding 에서 발견되지 않은 id 집합.

    안전 원칙:
    - 명시 선택 → confidence 게이트 면제(사용자가 리포트 검토 후 선택했으므로).
    - 저신뢰 loser 동일 청크 동반삭제 방지: protected_keys 검사를 적용한다.
      단, b_lines 가 있는 경우(라인 정밀 삭제)는 허용한다 —
      청크 전체가 아닌 특정 라인만 제거하므로 동반삭제 위험이 없다.
    - 혼합 청크: b_lines 있으면 라인 정밀 삭제, 없으면 제외 + 안내.
    - applier sha 스테일 검증은 불변(Operation 레벨에서 applier 가 보장).
    """
    from rune.review.applier import Operation

    # 저신뢰 loser 청크 키 집합 — 청크 전체 삭제(delete) 동반삭제 차단용.
    # b_lines(라인 정밀 삭제)는 이 검사를 통과시킨다.
    protected_keys = _build_protected_keys(conflicts)

    ops: list = []
    protected_skipped = 0
    line_precision_applied = 0
    matched_ids: set[str] = set()

    for c in conflicts:
        if c.id not in select_ids:
            continue
        matched_ids.add(c.id)
        # 혼합 청크 검사: text 가 비어 있으면 디스크에서 읽는다.
        chunk_text = c.b.text if c.b.text else _resolve_chunk_text(c.b)
        if chunk_text is None:
            # 확인 불가한 청크는 지우지 않는다(안전 원칙).
            protected_skipped += 1
            print(
                f"[select] {c.id}: 청크 본문 해석 불가 — 제외됨.",
                file=sys.stderr,
            )
            continue
        if _is_mixed_chunk(chunk_text):
            b_lines = getattr(c, "b_lines", None)
            if b_lines is not None:
                # 라인 정밀 삭제: 청크 전체가 아닌 특정 라인만 제거하므로
                # protected_keys 검사(동반삭제 방지)를 적용하지 않는다.
                ops.append(Operation(kind="delete_lines", ref=c.b, line_range=b_lines))
                line_precision_applied += 1
            else:
                protected_skipped += 1
                print(
                    f"[select] {c.id}: 혼합 청크 + b_lines 없음 — 라인 정밀 삭제 불가, 제외됨.",
                    file=sys.stderr,
                )
            continue
        # 청크 전체 삭제(delete) 경로: 저신뢰 loser 동반삭제 방지 검사 적용.
        # 단, 선택된 finding 자신이 그 저신뢰 충돌의 당사자인 경우는 허용한다
        # (사용자가 리포트를 검토 후 명시 선택했으므로 confidence 게이트 면제).
        # protected_keys 는 "선택되지 않은 다른 저신뢰 finding 의 loser 청크"를 보호하므로,
        # 해당 finding 이 select_ids 에 포함된 경우는 동반삭제가 아니라 명시 삭제다.
        key = _chunk_key(c.b)
        if key in protected_keys:
            # 이 청크를 loser 로 가지는 저신뢰 충돌 중 하나라도 select_ids 에 있으면 허용.
            loser_selected = any(
                _chunk_key(other.b) == key and other.id in select_ids
                for other in conflicts
                if other.confidence < APPLY_CONFLICT_CONFIDENCE_THRESHOLD
            )
            if not loser_selected:
                protected_skipped += 1
                print(
                    f"[select] {c.id}: 저신뢰 충돌의 loser 와 동일 청크 — "
                    f"통째 삭제 차단됨(동반삭제 방지).",
                    file=sys.stderr,
                )
                continue
        ops.append(Operation(kind="delete", ref=c.b))

    for d in dead:
        if d.id not in select_ids:
            continue
        matched_ids.add(d.id)
        dead_text = d.chunk.text if d.chunk.text else _resolve_chunk_text(d.chunk)
        if dead_text is None:
            protected_skipped += 1
            print(
                f"[select] {d.id}: 청크 본문 해석 불가 — 제외됨.",
                file=sys.stderr,
            )
            continue
        if _is_mixed_chunk(dead_text):
            protected_skipped += 1
            print(
                f"[select] {d.id}: 혼합 청크 — 제외됨.",
                file=sys.stderr,
            )
            continue
        ops.append(Operation(kind="delete", ref=d.chunk))

    unknown_ids = select_ids - matched_ids
    return ops, protected_skipped, line_precision_applied, unknown_ids


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
    confirm_delete_heuristics: bool = typer.Option(False, "--confirm-delete-heuristics", help="Acknowledge headless heuristic deletion; required for --apply --yes without --from-report."),
    from_report: Path = typer.Option(None, "--from-report", help="Load ops from a saved JSON report (produced by rune review --json). Live scan is skipped entirely; ops are built solely from the report's conflicts/dead_candidates."),
    select: str = typer.Option(None, "--select", help="Comma-separated finding IDs (c-XXXXXXXX or d-XXXXXXXX) to apply selectively. Use with --json output IDs. Confidence gate is waived for explicitly selected items; only line-precise or whole-chunk single-rule deletions are performed."),
    probe_startup_time: bool = typer.Option(False, "--probe-startup-time", hidden=True),
):
    import os
    backup_root = path / ".rune" / "backups"

    # (3) --select: 선택 id 파싱. 값이 주어지면 집합으로 보관해 이후 필터링에 사용.
    # unknown id 는 ops 구성 후 검증한다.
    select_ids: "frozenset[str] | None" = None
    if select is not None:
        parsed = frozenset(s.strip() for s in select.split(",") if s.strip())
        if not parsed:
            print("error: --select 에 유효한 id 가 없습니다.", file=sys.stderr)
            raise typer.Exit(2)
        select_ids = parsed

    # I6: --apply and --restore are mutually exclusive
    if apply and restore:
        print("error: --apply and --restore are mutually exclusive", file=sys.stderr)
        raise typer.Exit(2)

    if restore:
        snap = backup_root / restore
        if not snap.exists():
            print(f"snapshot not found: {restore}", file=sys.stderr)
            raise typer.Exit(2)
        # 재귀 순회: snap.iterdir() 는 평면 순회라 .claude/rules/* 처럼
        # 하위 디렉토리에 백업된 파일을 놓친다. rglob('*') 로 모든 깊이를 커버하고,
        # 파일만 대상으로 처리해 디렉토리 진입 시 IsADirectoryError 를 방지한다.
        for f in snap.rglob("*"):
            if not f.is_file():
                continue
            if f.name == "operation_log.json":
                continue
            relative = f.relative_to(snap)
            target = path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f.read_bytes())
        print(f"restored from {restore}")
        return

    if apply:
        if not yes:
            print("refusing to apply without --yes", file=sys.stderr)
            raise typer.Exit(2)

        # C4: gate --apply --yes behind explicit confirmation
        allow_blind = os.environ.get("RUNE_ALLOW_BLIND_APPLY") == "1"
        has_explicit_confirm = (
            confirm_delete_heuristics or
            from_report is not None or
            allow_blind
        )
        if not has_explicit_confirm:
            print(
                "error: --apply --yes requires explicit confirmation:\n"
                "  --confirm-delete-heuristics    (acknowledge headless heuristic deletion)\n"
                "  --from-report PATH             (apply ops from JSON report)\n"
                "  RUNE_ALLOW_BLIND_APPLY=1       (legacy automation escape)\n"
                "Refusing to delete content based on heuristics alone.",
                file=sys.stderr,
            )
            raise typer.Exit(2)

        # (2) --from-report: 리포트 파일에서 ops 를 구성한다. 라이브 스캔 완전 생략.
        # 과거 동작: from_report 를 확인 플래그로만 쓰고 실제로는 라이브 스캔 결과 사용.
        # 수정 동작: 파일을 실제 파싱하여 그 안의 conflicts/dead_candidates 만으로 ops 구성.
        if from_report is not None:
            if not from_report.exists():
                print(
                    f"error: --from-report 파일을 찾을 수 없습니다: {from_report}",
                    file=sys.stderr,
                )
                raise typer.Exit(2)
            try:
                report = _load_report_from_json(from_report)
            except Exception as exc:
                print(
                    f"error: --from-report 파일 파싱 실패: {exc}",
                    file=sys.stderr,
                )
                raise typer.Exit(2)
            apply_conflicts = report.conflicts
            apply_dead = report.dead_candidates
        else:
            # 라이브 스캔 경로
            refs_with_triggers = load_chunk_refs(path)
            refs = [r for r, _ in refs_with_triggers]
            apply_conflicts = find_lexical_conflicts(refs, repo_root=path)
            apply_dead = find_dead_rules_static(refs, repo_root=path)

            if events_path is not None:
                from rune.review.dead_events import find_dead_rules_events
                events_dead = find_dead_rules_events(
                    refs, events_path=events_path, window_days=events_window_days
                )
                apply_dead = apply_dead + events_dead

            if l2:
                from rune.review.conflict_nli import (
                    find_nli_conflicts,
                    build_l2_candidates,
                    DEFAULT_MODEL,
                    SMALL_MODEL,
                )
                model = SMALL_MODEL if nli_small else DEFAULT_MODEL
                candidates = build_l2_candidates(refs)
                nli_pairs = find_nli_conflicts(
                    candidates, model_name=model, allow_download=allow_model_download
                )
                apply_conflicts = apply_conflicts + nli_pairs

        if select_ids is not None:
            # --select 경로: confidence 게이트 면제, 지정 id 만 처리.
            ops, protected_skipped, line_precision_applied, unknown_ids = (
                _build_select_ops(apply_conflicts, apply_dead, select_ids)
            )
            # unknown id 가 있으면 즉시 종료(exit 2).
            if unknown_ids:
                for uid in sorted(unknown_ids):
                    print(f"error: unknown id '{uid}'", file=sys.stderr)
                raise typer.Exit(2)
            if protected_skipped:
                print(
                    f"보호/혼합 청크 {protected_skipped}건은 안전상 자동 삭제에서 제외됨 "
                    f"(report-only).",
                    file=sys.stderr,
                )
            if line_precision_applied:
                print(
                    f"혼합 청크 {line_precision_applied}건은 라인 정밀 삭제 적용 "
                    f"(충돌 유발 라인만 제거, 무관 규칙 보존).",
                    file=sys.stderr,
                )
        else:
            # (1)(4) 통합 게이트: 저신뢰·혼합·동반삭제·정적데드 필터 적용
            ops, low_confidence_skipped, protected_skipped, static_dead_skipped, line_precision_applied = (
                _build_apply_ops(apply_conflicts, apply_dead)
            )

            # 제외/적용 사유별 안내 — 안내 건수와 실제 처리 건수가 일치해야 한다.
            if low_confidence_skipped:
                print(
                    f"저신뢰 충돌 {low_confidence_skipped}건은 안전상 자동 삭제에서 제외됨 "
                    f"(confidence < {APPLY_CONFLICT_CONFIDENCE_THRESHOLD}; report-only).",
                    file=sys.stderr,
                )
            if protected_skipped:
                print(
                    f"보호/혼합 청크 {protected_skipped}건은 안전상 자동 삭제에서 제외됨 "
                    f"(report-only).",
                    file=sys.stderr,
                )
            if line_precision_applied:
                print(
                    f"혼합 청크 {line_precision_applied}건은 라인 정밀 삭제 적용 "
                    f"(충돌 유발 라인만 제거, 무관 규칙 보존).",
                    file=sys.stderr,
                )
            if static_dead_skipped:
                print(
                    f"정적 휴리스틱 데드 {static_dead_skipped}건은 report-only "
                    f"(사용 이벤트 확증(stage=events) 데드만 자동 삭제됨).",
                    file=sys.stderr,
                )

        from rune.review.applier import apply_operations, prune_backups
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

    # --apply 없는 경우: 라이브 스캔 후 리포트/TUI 출력
    # --select 가 지정되어 있지만 --apply 가 없으면 스캔 결과를 필터링 출력 후 exit 0.
    # (TUI를 실행하면 무한 대기가 발생하므로 --json 경로와 동일하게 처리한다.)
    if select_ids is not None:
        refs_with_triggers = load_chunk_refs(path)
        refs = [r for r, _ in refs_with_triggers]
        conflicts_scan = find_lexical_conflicts(refs, repo_root=path)
        dead_scan = find_dead_rules_static(refs, repo_root=path)
        report = ReviewReport(
            schema_version="1.0",
            detector_tier="L1",
            conflicts=[c for c in conflicts_scan if c.id in select_ids],
            dead_candidates=[d for d in dead_scan if d.id in select_ids],
        )
        print(jsonlib.dumps(report.to_dict(), indent=2))
        return

    refs_with_triggers = load_chunk_refs(path)
    refs = [r for r, _ in refs_with_triggers]
    conflicts = find_lexical_conflicts(refs, repo_root=path)
    dead = find_dead_rules_static(refs, repo_root=path)

    if events_path is not None:
        from rune.review.dead_events import find_dead_rules_events
        events_dead = find_dead_rules_events(refs, events_path=events_path, window_days=events_window_days)
        dead = dead + events_dead

    if l2:
        from rune.review.conflict_nli import (
            find_nli_conflicts,
            build_l2_candidates,
            DEFAULT_MODEL,
            SMALL_MODEL,
        )
        model = SMALL_MODEL if nli_small else DEFAULT_MODEL
        candidates = build_l2_candidates(refs)
        nli_pairs = find_nli_conflicts(
            candidates, model_name=model, allow_download=allow_model_download
        )
        conflicts = conflicts + nli_pairs
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
