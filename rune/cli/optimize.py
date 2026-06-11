"""rune optimize — tiered duplicate elimination via symlinks and chunk merging."""
import hashlib
import os
import shutil
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rune.pipeline.inventory import run_inventory
from rune.pipeline.dedup import find_dedup_pairs
from rune.pipeline.clustering import cluster_pairs
from rune.pipeline.tokenizer import count_tokens
from rune.models.source import InjectionSource

console = Console()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical(sources: list[InjectionSource]) -> InjectionSource:
    """Pick canonical: max tokens, then lexicographic path tiebreaker."""
    return max(sources, key=lambda s: (s.token_count, -len(str(s.path)), str(s.path)))


def _backup(path: Path, backup_root: Path) -> Path:
    rel = path.resolve().relative_to(Path.cwd().resolve()) if path.is_absolute() else path
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def _replace_with_symlink(target: Path, canonical: Path) -> None:
    if target.is_symlink():
        return
    rel = os.path.relpath(canonical.resolve(), start=target.parent.resolve())
    target.unlink()
    target.symlink_to(rel)


def _group_exact(sources: list[InjectionSource]) -> list[list[InjectionSource]]:
    groups: dict[str, list[InjectionSource]] = {}
    for s in sources:
        if s.path.is_symlink():
            continue
        try:
            groups.setdefault(_sha256(s.path), []).append(s)
        except OSError:
            continue
    return [g for g in groups.values() if len(g) >= 2]


def _group_semantic(
    sources: list[InjectionSource], threshold: float
) -> list[list[InjectionSource]]:
    if len(sources) < 2:
        return []
    pairs = find_dedup_pairs(sources)
    clusters = cluster_pairs(pairs, threshold)
    by_path: dict[Path, InjectionSource] = {s.path: s for s in sources}
    return [[by_path[p] for p in cluster if p in by_path] for cluster in clusters]


def _merge_chunks(
    sources: list[InjectionSource], target: Path, threshold: float
) -> tuple[int, int]:
    """Level 3 chunk-level dedup.

    Extracts paragraphs shared across two or more files into shared/_common.md,
    rewrites each original to reference the shared section by anchor.

    Returns (tokens_before, tokens_after).
    """
    from collections import defaultdict

    chunk_owners: dict[str, list[InjectionSource]] = defaultdict(list)
    chunk_text: dict[str, str] = {}
    chunk_tokens: dict[str, int] = {}

    for s in sources:
        if s.path.is_symlink():
            continue
        for c in s.chunks:
            normalized = c.text.strip()
            if len(normalized) < 32:
                continue
            key = hashlib.sha256(normalized.encode()).hexdigest()
            chunk_owners[key].append(s)
            chunk_text[key] = normalized
            chunk_tokens[key] = c.token_count

    shared_keys = [k for k, owners in chunk_owners.items() if len(owners) >= 2]
    if not shared_keys:
        return (0, 0)

    common_path = target / ".claude" / "shared" / "_common.md"
    common_path.parent.mkdir(parents=True, exist_ok=True)

    anchors: dict[str, str] = {}
    common_lines: list[str] = ["# Shared Content", ""]
    for i, key in enumerate(shared_keys):
        anchor = f"shared-{i + 1}"
        anchors[key] = anchor
        common_lines.append(f"<!-- rune:anchor {anchor} -->")
        common_lines.append(chunk_text[key])
        common_lines.append("")
    common_path.write_text("\n".join(common_lines))

    tokens_before = 0
    tokens_after = count_tokens(common_path.read_text())

    affected = {s.path: s for owners in chunk_owners.values() for s in owners if s.path in {x.path for x in sources}}
    for s in affected.values():
        if s.path.is_symlink():
            continue
        tokens_before += s.token_count
        new_lines: list[str] = []
        for c in s.chunks:
            normalized = c.text.strip()
            key = hashlib.sha256(normalized.encode()).hexdigest()
            if key in anchors:
                rel = os.path.relpath(common_path, start=s.path.parent)
                new_lines.append(f"<!-- rune:include {rel}#{anchors[key]} -->")
            else:
                new_lines.append(c.text)
            new_lines.append("")
        s.path.write_text("\n".join(new_lines).rstrip() + "\n")
        tokens_after += count_tokens(s.path.read_text())

    return (tokens_before, tokens_after)


def optimize_cmd(
    path: Path = typer.Argument(default=None, help="Project directory"),
    level: int = typer.Option(1, "--level", min=1, max=3, help="1=exact, 2=semantic-symlink, 3=chunk-merge"),
    threshold: float = typer.Option(None, "--threshold", help="Override cosine threshold (level 2/3)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
) -> None:
    """Optimize static instruction injection by collapsing duplicates."""
    target = (path or Path.cwd()).resolve()
    sources, _ = run_inventory(target)

    if not sources:
        console.print(f"[yellow]설정 없음[/yellow] — {target}")
        return

    total_before = sum(s.token_count for s in sources)
    threshold_eff = threshold if threshold is not None else {1: 1.0, 2: 0.98, 3: 0.92}[level]

    if level == 1:
        groups = _group_exact(sources)
    else:
        groups = _group_semantic(sources, threshold_eff)

    if not groups and level < 3:
        console.print(f"[green]최적화 대상 없음[/green] (level {level}, threshold {threshold_eff:.2f})")
        return

    backup_root = target / ".rune" / "backup" / time.strftime("%Y%m%d-%H%M%S")
    actions: list[tuple[Path, Path, int]] = []
    saved = 0

    for group in groups:
        canonical = _canonical(group)
        for s in group:
            if s.path == canonical.path:
                continue
            actions.append((s.path, canonical.path, s.token_count))
            saved += s.token_count

    table = Table(title=f"Level {level} optimization (threshold={threshold_eff:.2f})")
    table.add_column("source", style="dim")
    table.add_column("→ canonical")
    table.add_column("tokens", justify="right")
    for src, canon, tok in actions:
        try:
            src_rel = src.relative_to(target)
            canon_rel = canon.relative_to(target)
        except ValueError:
            src_rel, canon_rel = src, canon
        table.add_row(str(src_rel), str(canon_rel), str(tok))
    if actions:
        console.print(table)

    if level == 3:
        chunks_before, chunks_after = _merge_chunks(sources, target, threshold_eff) if not dry_run else (0, 0)
        if not dry_run and chunks_before:
            chunk_saved = chunks_before - chunks_after
            saved += chunk_saved
            console.print(f"[cyan]Chunk merge[/cyan]: {chunks_before} → {chunks_after} tokens (saved {chunk_saved})")

    if dry_run:
        console.print(f"\n[bold]DRY RUN[/bold] — 예상 절약: [green]{saved:,}[/green] tokens")
        console.print(f"전: {total_before:,} → 후 예상: {total_before - saved:,}")
        return

    backup_root.mkdir(parents=True, exist_ok=True)
    for src, canon, _tok in actions:
        try:
            _backup(src, backup_root)
            _replace_with_symlink(src, canon)
        except OSError as e:
            console.print(f"[red]skip[/red] {src}: {e}")

    console.print(f"\n[bold green]완료[/bold green] — 절약: {saved:,} tokens")
    console.print(f"전: {total_before:,} → 후: {total_before - saved:,}")
    console.print(f"백업: {backup_root.relative_to(target) if backup_root.is_relative_to(target) else backup_root}")
