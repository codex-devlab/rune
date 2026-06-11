import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchEntry:
    target_path: str
    pre_sha256: str
    post_sha256: str
    payload_path: str
    description: str
    applied_at_iso: str


def load_manifest(path: Path) -> list[PatchEntry]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [PatchEntry(**p) for p in data.get("patch", [])]


def _file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_entry(entry: PatchEntry, base_dir: Path) -> str:
    target = Path(entry.target_path)
    if not target.is_absolute():
        target = base_dir / target
    if not target.exists():
        return "MISSING"
    actual = _file_sha256(target)
    if actual == entry.pre_sha256 or actual == entry.post_sha256:
        return "OK"
    return f"DRIFT (expected {entry.pre_sha256} or {entry.post_sha256}, got {actual})"
