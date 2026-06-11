import subprocess
from pathlib import Path


def test_patch_verify_reports_ok(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("x")
    import hashlib
    sha = hashlib.sha256(b"x").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = "{sha}"
post_sha256 = "yyy"
payload_path = ""
description = ""
applied_at_iso = ""
""")
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout
