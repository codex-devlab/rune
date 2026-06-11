import hashlib
from pathlib import Path
from rune.patches.manifest import PatchEntry, load_manifest, verify_entry

def test_load_manifest_minimal(tmp_path):
    manifest = tmp_path / "manifest.toml"
    manifest.write_text("""
[[patch]]
target_path = "rune/cli/main.py"
pre_sha256 = "abc"
post_sha256 = "def"
payload_path = "rune/patches/payloads/p001.py"
description = "register review"
applied_at_iso = "2026-06-11T00:00:00Z"
""")
    entries = load_manifest(manifest)
    assert len(entries) == 1
    assert entries[0].target_path == "rune/cli/main.py"
    assert entries[0].pre_sha256 == "abc"

def test_verify_entry_ok(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    entry = PatchEntry(
        target_path=str(target),
        pre_sha256=sha,
        post_sha256="xxx",
        payload_path="",
        description="",
        applied_at_iso="",
    )
    assert verify_entry(entry, base_dir=tmp_path) == "OK"

def test_verify_entry_drift(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("hello")
    entry = PatchEntry(
        target_path=str(target),
        pre_sha256="0" * 64,
        post_sha256="xxx",
        payload_path="",
        description="",
        applied_at_iso="",
    )
    result = verify_entry(entry, base_dir=tmp_path)
    assert result.startswith("DRIFT")
