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


def find_dead_rules_static(refs: list[ChunkRef], repo_root: Path) -> list[DeadCandidate]:
    if not refs:
        return []
    # Pre-walk repo ONCE
    all_files = [p for p in repo_root.rglob("*") if p.is_file()]
    exts_present: set[str] = {p.suffix for p in all_files}
    path_strs_lower: list[str] = [str(p).lower() for p in all_files]

    dead: list[DeadCandidate] = []
    for ref in refs:
        keywords = _trigger_keywords(ref.text)
        if not keywords:
            continue
        alive = False
        for kw in keywords:
            exts = LANG_TO_EXT.get(kw)
            if exts and any(ext in exts_present for ext in exts):
                alive = True
                break
            if any(kw in s for s in path_strs_lower):
                alive = True
                break
        if not alive:
            dead.append(DeadCandidate(
                chunk=ref,
                reason=f"trigger keywords {keywords} not found in repo",
                stage="static",
            ))
    return dead
