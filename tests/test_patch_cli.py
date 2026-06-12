import hashlib
import subprocess
import time
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
    assert "PENDING" in result.stdout or "APPLIED" in result.stdout


def test_patch_verify_reports_applied(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("x")
    sha = hashlib.sha256(b"x").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = "aaa"
post_sha256 = "{sha}"
payload_path = ""
description = ""
applied_at_iso = ""
""")
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "APPLIED" in result.stdout


def test_patch_apply_writes_payload(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("before")
    payload = tmp_path / "p.py"
    payload.write_text("after")
    pre = hashlib.sha256(b"before").hexdigest()
    post = hashlib.sha256(b"after").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = "{pre}"
post_sha256 = "{post}"
payload_path = "{payload}"
description = "test"
applied_at_iso = "2026-06-11T00:00:00Z"
""")
    result = subprocess.run(
        ["rune", "patch", "apply", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert target.read_text() == "after"


def test_patch_apply_creates_new_file(tmp_path):
    payload = tmp_path / "payload.py"
    payload.write_text("brand new content")
    post = hashlib.sha256(b"brand new content").hexdigest()
    target = tmp_path / "subdir" / "new_module.py"  # doesn't exist
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = ""
post_sha256 = "{post}"
payload_path = "{payload}"
description = "create new module"
applied_at_iso = "2026-06-11T00:00:00Z"
""")
    result = subprocess.run(
        ["rune", "patch", "apply", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert target.read_text() == "brand new content"


def test_patch_apply_rejects_corrupted_payload(tmp_path):
    payload = tmp_path / "p.py"
    payload.write_text("real content")
    target = tmp_path / "t.py"
    # Lie about post_sha — claim payload matches "fake content" but wrote "real content"
    wrong_post = hashlib.sha256(b"fake content").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = ""
post_sha256 = "{wrong_post}"
payload_path = "{payload}"
description = "test"
applied_at_iso = "2026-06-12T00:00:00Z"
""")
    result = subprocess.run(
        ["rune", "patch", "apply", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "PAYLOAD MISMATCH" in result.stderr or "PAYLOAD MISMATCH" in result.stdout
    assert not target.exists()  # apply must NOT create the file


def test_patch_verify_perf_20_entries(tmp_path):
    files = [tmp_path / f"f{i}.py" for i in range(20)]
    for f in files:
        f.write_text("x")
    sha = hashlib.sha256(b"x").hexdigest()
    entries_toml = "\n".join(
        f'[[patch]]\ntarget_path = "{f}"\npre_sha256 = "{sha}"\npost_sha256 = "y"\n'
        f'payload_path = ""\ndescription = ""\napplied_at_iso = ""'
        for f in files
    )
    manifest = tmp_path / "m.toml"
    manifest.write_text(entries_toml)
    t0 = time.perf_counter()
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(manifest)],
        capture_output=True, text=True,
    )
    elapsed = time.perf_counter() - t0
    assert result.returncode == 0
    assert elapsed < 0.5, f"verify took {elapsed:.3f}s"
