import re
from pathlib import Path
from rune.review.types import ChunkRef, DeadCandidate

TRIGGER_RE = re.compile(r"(?i)^trigger:\s*(.+)$", re.MULTILINE)

LANG_TO_EXT = {
    "golang": [".go"], "go": [".go"],
    "python": [".py"], "py": [".py"],
    "typescript": [".ts", ".tsx"], "ts": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"], "js": [".js", ".jsx"],
    "rust": [".rs"], "swift": [".swift"], "kotlin": [".kt"],
    "react": [".tsx", ".jsx"],
}


def _trigger_keywords(text: str) -> list[str]:
    m = TRIGGER_RE.search(text)
    if not m:
        return []
    return [k.strip().lower() for k in m.group(1).split(",") if k.strip()]


def _repo_has_extension(repo_root: Path, exts: list[str]) -> bool:
    for ext in exts:
        if any(True for _ in repo_root.rglob(f"*{ext}")):
            return True
    return False


def find_dead_rules_static(refs: list[ChunkRef], repo_root: Path) -> list[DeadCandidate]:
    dead: list[DeadCandidate] = []
    for ref in refs:
        keywords = _trigger_keywords(ref.text)
        if not keywords:
            continue
        alive = False
        for kw in keywords:
            exts = LANG_TO_EXT.get(kw)
            if exts and _repo_has_extension(repo_root, exts):
                alive = True
                break
            if any(kw in str(p).lower() for p in repo_root.rglob("*") if p.is_file()):
                alive = True
                break
        if not alive:
            dead.append(DeadCandidate(
                chunk=ref,
                reason=f"trigger keywords {keywords} not found in repo",
                stage="static",
            ))
    return dead
