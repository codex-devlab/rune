"""
tests/test_fix_blocker_patch.py

patch-manifest 그룹 소유 테스트.

검증 범위:
  - --manifest 인자 없는 verify / apply 가 exit 0 으로 종료 (번들 매니페스트 사용)
  - 빈 엔트리 매니페스트 분기: "no patches" + exit 0
  - 존재하지 않는 매니페스트 경로 분기: "no patches" + exit 0
  - --manifest 명시 경로의 기존 동작 회귀 없음
    (기존 test_patch_cli.py 가 이미 --manifest 경로를 커버하므로 핵심 케이스만 추가)
  - BUNDLED_MANIFEST 상수가 올바른 위치를 가리키는지 단위 확인
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from rune.patches.manifest import BUNDLED_MANIFEST


# ---------------------------------------------------------------------------
# 번들 매니페스트 상수 단위 테스트
# ---------------------------------------------------------------------------

def test_bundled_manifest_points_to_correct_path():
    """BUNDLED_MANIFEST 는 rune/patches/manifest.toml 을 가리켜야 한다."""
    assert BUNDLED_MANIFEST.name == "manifest.toml"
    assert BUNDLED_MANIFEST.parent.name == "patches"
    # 패키지가 editable 설치되어 있으므로 파일이 실제로 존재해야 한다.
    assert BUNDLED_MANIFEST.exists(), f"번들 매니페스트 파일 누락: {BUNDLED_MANIFEST}"


# ---------------------------------------------------------------------------
# 인자 없는 verify / apply — 번들 매니페스트(0 엔트리) 경로
# ---------------------------------------------------------------------------

def _run_patch(subcmd: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "rune.cli.main", "patch", subcmd]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
    )


def test_verify_no_manifest_arg_exits_zero():
    """--manifest 없이 'rune patch verify' 호출 시 exit 0 이어야 한다."""
    result = subprocess.run(
        ["rune", "patch", "verify"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "no patches" in result.stdout.lower()


def test_apply_no_manifest_arg_exits_zero():
    """--manifest 없이 'rune patch apply' 호출 시 exit 0 이어야 한다."""
    result = subprocess.run(
        ["rune", "patch", "apply"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "no patches" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 빈 엔트리 매니페스트 — [[patch]] 섹션이 없는 파일
# ---------------------------------------------------------------------------

def test_verify_empty_manifest_exits_zero(tmp_path):
    """[[patch]] 엔트리가 없는 매니페스트로 verify 시 exit 0 + 'no patches'."""
    empty = tmp_path / "empty.toml"
    empty.write_text("# 엔트리 없음\n")
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(empty)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "no patches" in result.stdout.lower()


def test_apply_empty_manifest_exits_zero(tmp_path):
    """[[patch]] 엔트리가 없는 매니페스트로 apply 시 exit 0 + 'no patches'."""
    empty = tmp_path / "empty.toml"
    empty.write_text("# 엔트리 없음\n")
    result = subprocess.run(
        ["rune", "patch", "apply", "--manifest", str(empty)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "no patches" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 존재하지 않는 --manifest 경로
# ---------------------------------------------------------------------------

def test_verify_missing_manifest_file_exits_zero(tmp_path):
    """지정한 --manifest 파일이 없을 때 exit 0 + 'no patches'."""
    missing = tmp_path / "nonexistent.toml"
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "no patches" in result.stdout.lower()


def test_apply_missing_manifest_file_exits_zero(tmp_path):
    """지정한 --manifest 파일이 없을 때 exit 0 + 'no patches'."""
    missing = tmp_path / "nonexistent.toml"
    result = subprocess.run(
        ["rune", "patch", "apply", "--manifest", str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "no patches" in result.stdout.lower()


# ---------------------------------------------------------------------------
# --manifest 명시 경로 회귀: PENDING / APPLIED 분기 각각 exit 0
# ---------------------------------------------------------------------------

def test_verify_explicit_manifest_pending(tmp_path):
    """--manifest 명시 + PENDING 엔트리 → exit 0."""
    target = tmp_path / "t.py"
    target.write_text("hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = "{sha}"
post_sha256 = "{"y" * 64}"
payload_path = ""
description = ""
applied_at_iso = ""
""")
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(manifest)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PENDING" in result.stdout


def test_verify_explicit_manifest_applied(tmp_path):
    """--manifest 명시 + APPLIED 엔트리 → exit 0, 출력에 OK 포함."""
    target = tmp_path / "t.py"
    target.write_text("hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    manifest = tmp_path / "m.toml"
    manifest.write_text(f"""
[[patch]]
target_path = "{target}"
pre_sha256 = "{"a" * 64}"
post_sha256 = "{sha}"
payload_path = ""
description = ""
applied_at_iso = ""
""")
    result = subprocess.run(
        ["rune", "patch", "verify", "--manifest", str(manifest)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # verify_cmd 는 APPLIED 를 "OK" 로 보고한다.
    assert "OK" in result.stdout
