import hashlib
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer

from rune.patches.manifest import BUNDLED_MANIFEST, load_manifest, verify_entry

patch_app = typer.Typer(help="Patch journal commands")


def _resolve_manifest(manifest: Optional[Path]) -> Path:
    """--manifest 미지정 시 번들된 기본 매니페스트를 반환한다."""
    return manifest if manifest is not None else BUNDLED_MANIFEST


@patch_app.command("verify")
def verify_cmd(manifest: Optional[Path] = typer.Option(None, "--manifest")):
    manifest = _resolve_manifest(manifest)
    # 파일 자체가 없으면 패치 없음으로 정상 종료 (설치 환경에서 번들 누락 방어)
    if not manifest.exists():
        print("no patches")
        raise typer.Exit(0)
    entries = load_manifest(manifest)
    if not entries:
        print("no patches")
        raise typer.Exit(0)
    base_dir = manifest.parent
    exit_code = 0
    for entry in entries:
        status = verify_entry(entry, base_dir=base_dir)
        # APPLIED 는 정상이므로 OK 로 보고한다.
        reported = "OK" if status == "APPLIED" else status
        print(f"{entry.target_path}: {reported}")
        if status not in ("APPLIED", "PENDING"):
            exit_code = 1
    raise typer.Exit(exit_code)


@patch_app.command("apply")
def apply_cmd(
    manifest: Optional[Path] = typer.Option(None, "--manifest"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    manifest = _resolve_manifest(manifest)
    # 파일 자체가 없으면 패치 없음으로 정상 종료
    if not manifest.exists():
        print("no patches")
        raise typer.Exit(0)
    entries = load_manifest(manifest)
    if not entries:
        print("no patches")
        raise typer.Exit(0)
    # 상대 경로는 매니페스트 위치 기준으로 해석한다 (verify_cmd 와 동일한 규칙).
    base_dir = manifest.parent
    for entry in entries:
        target = Path(entry.target_path)
        if not target.is_absolute():
            target = base_dir / target
        payload = Path(entry.payload_path)
        if not payload.is_absolute():
            payload = base_dir / payload
        # New-file case: pre_sha256 is empty and target doesn't exist yet
        if entry.pre_sha256 == "" and not target.exists():
            if dry_run:
                print(f"WOULD CREATE: {target}")
                continue
            if not payload.exists():
                print(f"PAYLOAD MISSING: {payload}", file=sys.stderr)
                raise typer.Exit(2)
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
        if not payload.exists():
            print(f"PAYLOAD MISSING: {payload}", file=sys.stderr)
            raise typer.Exit(2)
        payload_sha = hashlib.sha256(payload.read_bytes()).hexdigest()
        if payload_sha != entry.post_sha256:
            print(
                f"PAYLOAD MISMATCH: {payload} expected {entry.post_sha256} got {payload_sha}",
                file=sys.stderr,
            )
            raise typer.Exit(2)
        shutil.copy2(payload, target)
        print(f"APPLIED: {target}")
