"""
Generate TOML manifest for rune v0.2 deployment.

Usage:
  python scripts/build_manifest.py --target-root <dir> [--manifest <out.toml>]

For real site-packages deployment, --target-root would be
/opt/homebrew/lib/python3.11/site-packages/rune/. For verification, pass a temp dir.
"""
import argparse
import hashlib
import shutil
from pathlib import Path

import tomli_w


def discover_targets(dev_root: Path) -> list[str]:
    """Auto-discover deployable files.

    Includes all of rune/review/* and rune/patches/* (whole modules added by v0.2).
    Plus surgical-edit files explicitly listed (cli/*, adapters/*, pipeline/clustering.py).
    """
    surgical = [
        "cli/main.py", "cli/patch.py", "cli/optimize.py",
        "pipeline/clustering.py",
        "adapters/generic.py", "adapters/claude_code.py",
    ]
    targets: list[str] = list(surgical)

    for module_dir in ("review", "patches"):
        for p in sorted((dev_root / module_dir).rglob("*")):
            if p.is_file() and p.suffix in {".py", ".json", ".md"}:
                if "__pycache__" in p.parts:
                    continue
                if "payloads" in p.parts:  # generated artifacts
                    continue
                targets.append(str(p.relative_to(dev_root)))
    return targets


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-root", type=Path, required=True,
                    help="Destination directory mimicking site-packages/rune/ layout")
    ap.add_argument("--dev-root", type=Path,
                    default=Path(__file__).resolve().parent.parent / "rune",
                    help="Dev clone rune package root")
    ap.add_argument("--manifest", type=Path,
                    default=Path(__file__).resolve().parent.parent / "rune" / "patches" / "manifest.toml")
    ap.add_argument("--payload-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "rune" / "patches" / "payloads")
    args = ap.parse_args()

    args.payload_dir.mkdir(parents=True, exist_ok=True)

    targets = discover_targets(args.dev_root)
    entries = []
    for rel in targets:
        target = args.target_root / rel
        dev = args.dev_root / rel
        if not dev.exists():
            print(f"WARN: dev file missing, skipping: {dev}")
            continue
        pre = sha256(target) if target.exists() else ""
        post = sha256(dev)
        payload_name = rel.replace("/", "__")
        payload_dst = args.payload_dir / payload_name
        shutil.copyfile(dev, payload_dst)
        entries.append({
            "target_path": str(target),
            "pre_sha256": pre,
            "post_sha256": post,
            "payload_path": str(payload_dst),
            "description": rel,
            "applied_at_iso": "",
        })

    with open(args.manifest, "wb") as f:
        tomli_w.dump({"patch": entries}, f)
    print(f"manifest written: {args.manifest} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
