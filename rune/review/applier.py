import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from rune.review.types import ChunkRef


class StaleChunkError(Exception):
    pass


@dataclass
class Operation:
    kind: str  # "delete" | "comment" | "keep"
    ref: ChunkRef


def _read_chunk(path: Path, start: int, end: int) -> str:
    lines = path.read_text().splitlines(keepends=True)
    return "".join(lines[start - 1:end])


def _backup_file(file: Path, backup_root: Path) -> Path:
    rel = file.name
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, dst)
    return dst


def apply_operations(ops: list[Operation], backup_dir: Path) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_root = backup_dir / timestamp
    snapshot_root.mkdir(parents=True, exist_ok=True)
    log = {"timestamp": timestamp, "ops": []}
    # Group ops by file
    by_file: dict[Path, list[Operation]] = {}
    for op in ops:
        by_file.setdefault(op.ref.path, []).append(op)
    for path, file_ops in by_file.items():
        # Verify staleness for every op first
        for op in file_ops:
            current = _read_chunk(path, op.ref.start_line, op.ref.end_line).rstrip("\n")
            current_sha = hashlib.sha256(current.encode("utf-8")).hexdigest()
            if current_sha != op.ref.sha256:
                raise StaleChunkError(f"file changed since scan: {path}")
        _backup_file(path, snapshot_root)
        # Apply in reverse line order
        file_ops.sort(key=lambda o: o.ref.start_line, reverse=True)
        lines = path.read_text().splitlines(keepends=True)
        for op in file_ops:
            if op.kind == "delete":
                del lines[op.ref.start_line - 1:op.ref.end_line]
            elif op.kind == "comment":
                for i in range(op.ref.start_line - 1, op.ref.end_line):
                    lines[i] = "<!-- " + lines[i].rstrip("\n") + " -->\n"
            log["ops"].append({
                "file": str(path), "kind": op.kind,
                "start_line": op.ref.start_line, "end_line": op.ref.end_line,
            })
        path.write_text("".join(lines))
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
