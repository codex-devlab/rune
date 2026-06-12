import hashlib
import shutil
import sys
from pathlib import Path

import typer

from rune.patches.manifest import load_manifest, verify_entry

patch_app = typer.Typer(help="Patch journal commands")


@patch_app.command("verify")
def verify_cmd(manifest: Path = typer.Option(..., "--manifest")):
    entries = load_manifest(manifest)
    base_dir = manifest.parent
    exit_code = 0
    for entry in entries:
        status = verify_entry(entry, base_dir=base_dir)
        print(f"{entry.target_path}: {status}")
        if status not in ("APPLIED", "PENDING"):
            exit_code = 1
    raise typer.Exit(exit_code)


@patch_app.command("apply")
def apply_cmd(
    manifest: Path = typer.Option(..., "--manifest"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    entries = load_manifest(manifest)
    for entry in entries:
        target = Path(entry.target_path)
        payload = Path(entry.payload_path)
        # New-file case: pre_sha256 is empty and target doesn't exist yet
        if entry.pre_sha256 == "" and not target.exists():
            if dry_run:
                print(f"WOULD CREATE: {target}")
                continue
            payload_sha = hashlib.sha256(payload.read_bytes()).hexdigest()
            if payload_sha != entry.post_sha256:
                print(
                    f"PAYLOAD MISMATCH: {payload} expected {entry.post_sha256} got {payload_sha}",
                    file=sys.stderr,
                )
                raise typer.Exit(2)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(payload, target)
            print(f"CREATED: {target}")
            continue
        if not target.exists():
            print(f"MISSING: {target}")
            raise typer.Exit(1)
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual == entry.post_sha256:
            print(f"SKIP (already applied): {target}")
            continue
        if actual != entry.pre_sha256:
            print(f"DRIFT: {target} expected {entry.pre_sha256} got {actual}")
            raise typer.Exit(2)
        if dry_run:
            print(f"WOULD APPLY: {target}")
            continue
        payload_sha = hashlib.sha256(payload.read_bytes()).hexdigest()
        if payload_sha != entry.post_sha256:
            print(
                f"PAYLOAD MISMATCH: {payload} expected {entry.post_sha256} got {payload_sha}",
                file=sys.stderr,
            )
            raise typer.Exit(2)
        shutil.copy2(payload, target)
        print(f"APPLIED: {target}")
