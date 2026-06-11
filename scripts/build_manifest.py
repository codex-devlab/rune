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


TARGETS = [
    "cli/main.py",
    # v0.2 review
    "review/__init__.py", "review/cli.py", "review/types.py", "review/loader.py",
    "review/conflict_lexical.py", "review/conflict_nli.py",
    "review/dead_static.py", "review/dead_events.py",
    "review/applier.py", "review/tui.py",
    "review/schema.json", "review/SCHEMA_POLICY.md",
    "review/L1_LIMITS.md", "review/BENCHMARKS.md",
    # patch journal
    "cli/patch.py",
    "patches/__init__.py", "patches/manifest.py",
    # optimize (ported from prior session)
    "cli/optimize.py", "pipeline/clustering.py",
    "adapters/generic.py", "adapters/claude_code.py",
]


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

    entries = []
    for rel in TARGETS:
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
