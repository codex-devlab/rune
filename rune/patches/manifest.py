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


_REQUIRED_FIELDS = ("target_path", "pre_sha256", "post_sha256", "payload_path", "description", "applied_at_iso")


def load_manifest(path: Path) -> list[PatchEntry]:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"malformed TOML in {path}: {e}") from e
    entries = []
    for i, p in enumerate(data.get("patch", [])):
        for field in _REQUIRED_FIELDS:
            if field not in p:
                raise ValueError(f"manifest entry {i} missing required field: {field}")
        entries.append(PatchEntry(**p))
    return entries


def _file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_entry(entry: PatchEntry, base_dir: Path) -> str:
    target = Path(entry.target_path)
    if not target.is_absolute():
        target = base_dir / target
    if not target.exists():
        return "MISSING"
    actual = _file_sha256(target)
    if actual == entry.post_sha256:
        return "APPLIED"
    if actual == entry.pre_sha256:
        return "PENDING"
    return f"DRIFT (expected {entry.pre_sha256} or {entry.post_sha256}, got {actual})"
