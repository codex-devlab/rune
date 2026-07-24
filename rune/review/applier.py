"""
Canonical chunk form is producer-defined in `rune/pipeline/tokenizer.py::split_into_chunks`
which applies `para.strip()` per paragraph. Any consumer that hashes chunk text MUST
mirror this transform (`.strip()`). Partial normalization (e.g., `.rstrip("\\n")` only) is
a bug — it produces SHA mismatches on chunks with trailing whitespace or CRLF endings.
"""
import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from rune.review.types import ChunkRef

_CHUNK_CANONICAL = "strip"  # signals producer-mirror invariant for any future hash-site


class StaleChunkError(Exception):
    pass


@dataclass
class Operation:
    kind: str  # "delete" | "delete_lines" | "comment" | "keep"
    ref: ChunkRef
    # delete_lines 전용: 실제 삭제할 라인 레인지(1-based inclusive).
    # kind=="delete_lines" 일 때만 유효. None 이면 ref 전체 범위를 사용.
    line_range: "tuple[int, int] | None" = None


def _op_sort_key(o: "Operation") -> int:
    """역순 정렬 기준: delete_lines 는 line_range 시작, 나머지는 ref 시작 라인."""
    if o.kind == "delete_lines" and o.line_range is not None:
        return o.line_range[0]
    return o.ref.start_line


def _read_chunk_from_lines(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1:end])


def _backup_file(file: Path, backup_root: Path, base_root: Path) -> Path:
    relative_path = file.relative_to(base_root)
    dst = backup_root / relative_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, dst)
    return dst


def apply_operations(ops: list[Operation], backup_dir: Path, base_root: Path) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_root = backup_dir / timestamp
    snapshot_root.mkdir(parents=True, exist_ok=True)
    log = {"timestamp": timestamp, "ops": []}
    # Group ops by file
    by_file: dict[Path, list[Operation]] = {}
    for op in ops:
        by_file.setdefault(op.ref.path, []).append(op)

    # Phase 1: PREPARE — read, verify, apply edits in memory, write tmp files, fsync.
    # No observable state change to target files yet.
    prepared: list[tuple[Path, Path, list[str]]] = []  # (target, tmp, edited_lines)
    try:
        for path, file_ops in by_file.items():
            lines = path.read_text().splitlines(keepends=True)  # ONCE per file (I4)
            # I5: bounds check — validate every op's range before touching anything
            for op in file_ops:
                if not (1 <= op.ref.start_line <= op.ref.end_line <= len(lines)):
                    raise ValueError(
                        f"chunk line range {op.ref.start_line}-{op.ref.end_line} out of bounds "
                        f"for {path} (file has {len(lines)} lines)"
                    )
                # delete_lines 전용: line_range 범위도 파일 범위 내에 있어야 한다.
                if op.kind == "delete_lines" and op.line_range is not None:
                    lr_start, lr_end = op.line_range
                    if not (1 <= lr_start <= lr_end <= len(lines)):
                        raise ValueError(
                            f"delete_lines line_range {lr_start}-{lr_end} out of bounds "
                            f"for {path} (file has {len(lines)} lines)"
                        )
                    # delete_lines line_range 는 ref 청크 범위 내에 있어야 한다.
                    # --from-report JSON의 b_lines 조작으로 임의 라인이 삭제되는 것을 방지.
                    # (sha256 스테일 검증은 ref 청크 기준이므로, line_range가 ref 밖이면
                    #  '안내와 실제 삭제 결과 불일치' — v0.2 안전 계약 위반)
                    if not (op.ref.start_line <= lr_start <= lr_end <= op.ref.end_line):
                        raise ValueError(
                            f"delete_lines line_range {lr_start}-{lr_end} outside ref bounds "
                            f"{op.ref.start_line}-{op.ref.end_line} for {path}"
                        )
            # C1: Verify staleness using producer-canonical .strip()
            # delete_lines 도 청크 전체 sha256 로 스테일 검증(안전망 동일).
            for op in file_ops:
                current = _read_chunk_from_lines(lines, op.ref.start_line, op.ref.end_line).strip()
                current_sha = hashlib.sha256(current.encode("utf-8")).hexdigest()
                if current_sha != op.ref.sha256:
                    raise StaleChunkError(f"file changed since scan: {path}")
            # C3: backup preserving relative path — done during prepare so snapshot
            # exists even if the commit phase crashes
            _backup_file(path, snapshot_root, base_root=base_root)
            # Apply in reverse line order (same lines list — I4).
            # delete_lines 는 line_range 기준, 나머지는 ref 기준으로 역순 정렬.
            file_ops.sort(key=_op_sort_key, reverse=True)
            for op in file_ops:
                if op.kind == "delete":
                    del lines[op.ref.start_line - 1:op.ref.end_line]
                elif op.kind == "delete_lines":
                    # 라인 정밀 삭제: line_range 라인만 제거.
                    # sha256 스테일 검증은 청크 전체 기준으로 이미 완료.
                    lr_start, lr_end = op.line_range if op.line_range else (op.ref.start_line, op.ref.end_line)
                    del lines[lr_start - 1:lr_end]
                    # 삭제 후 빈 줄 정리: delete 와 동일 원칙 — 연속 빈 줄 방지.
                    # 삭제된 위치(lr_start-1) 전후 빈 줄을 최대 1개로 정리한다.
                    pos = lr_start - 1
                    while pos > 0 and pos < len(lines):
                        prev_blank = pos > 0 and lines[pos - 1].strip() == ""
                        curr_blank = lines[pos].strip() == ""
                        if prev_blank and curr_blank:
                            del lines[pos]
                        else:
                            break
                elif op.kind == "comment":
                    for i in range(op.ref.start_line - 1, op.ref.end_line):
                        lines[i] = "<!-- " + lines[i].rstrip("\n") + " -->\n"
                # operation_log 에 kind 와 실제 삭제 라인 범위를 기록(additive).
                op_entry: dict = {
                    "file": str(path), "kind": op.kind,
                    "start_line": op.ref.start_line, "end_line": op.ref.end_line,
                }
                if op.kind == "delete_lines" and op.line_range is not None:
                    op_entry["line_range"] = list(op.line_range)
                log["ops"].append(op_entry)
            # Write tmp file with edited content; fsync to commit to disk
            tmp = path.with_suffix(path.suffix + ".rune-apply-tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("".join(lines))
                f.flush()
                os.fsync(f.fileno())
            prepared.append((path, tmp, lines))
    except Exception:
        # Cleanup any tmp files written so far before re-raising
        for _, tmp, _ in prepared:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise

    # Phase 2: COMMIT — atomic os.replace per file (POSIX-atomic within same filesystem).
    # If a rename fails mid-loop, the operation log records what was planned;
    # --restore can recover from the backup snapshot.
    for target, tmp, _ in sorted(prepared, key=lambda t: str(t[0])):
        os.replace(tmp, target)

    import json as _json
    (snapshot_root / "operation_log.json").write_text(_json.dumps(log, indent=2))
    return log


def prune_backups(backup_dir: Path, keep: int = 10) -> int:
    if not backup_dir.exists():
        return 0
    snaps = sorted([p for p in backup_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    to_remove = snaps[:-keep] if len(snaps) > keep else []
    for p in to_remove:
        shutil.rmtree(p)
    return len(to_remove)
