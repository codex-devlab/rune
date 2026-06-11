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
        if status != "OK":
            exit_code = 1
    raise typer.Exit(exit_code)
