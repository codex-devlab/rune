"""optimize-consistency 회귀 테스트.

핵심: analyze 가 추천한 경로를 사용자가 그대로 실행하면 0이 아닌 실제 절약 또는
정확한 다음 단계 안내를 받아야 한다. "추천했는데 0 절약 + 완료" 조합을 제거한다.
"""
import json
import re
from pathlib import Path

from typer.testing import CliRunner

from rune.cli.main import app
from rune.cli.optimize import recommended_optimize_command
from rune.pipeline.inventory import run_inventory

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Rich 가 삽입한 ANSI 스타일 코드를 제거해 순수 텍스트를 얻는다.

    Rich 는 '--level 3 --dry-run' 같은 문자열에서 숫자에 별도 스타일을 입혀
    토큰 사이에 escape sequence 를 끼워 넣으므로, 부분 문자열 검사 전에 제거한다.
    """
    return _ANSI.sub("", text)


def _chunk_dup_project(tmp_path: Path) -> Path:
    """청크(규칙) 단위 중복만 있는 프로젝트(파일 전체는 서로 다름)."""
    tdd = (
        "Always use TDD. Write a failing test first, then implement the minimal "
        "code to pass it, then refactor."
    )
    (tmp_path / "CLAUDE.md").write_text(
        "# Project Guidelines\n\n"
        f"{tdd}\n\n"
        "Be concise in code reviews and prefer small pull requests.\n"
    )
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "x.md").write_text(
        "## Testing Rules\n\n"
        f"{tdd}\n\n"
        "Keep test files next to the code they cover.\n"
    )
    return tmp_path


def _exact_dup_project(tmp_path: Path) -> Path:
    """완전 동일 파일 2개(심링크 병합 대상) — level 1 이 실제로 절약한다."""
    content = (
        "## Git Rules\n\nTrigger: git, commit, push\n\n"
        "Never force push main. Always write descriptive commit messages. "
        "Squash fixup commits before merging.\n"
    )
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "git.md").write_text(content)
    (rules / "git_copy.md").write_text(content)
    return tmp_path


def _no_dup_project(tmp_path: Path) -> Path:
    (tmp_path / "CLAUDE.md").write_text(
        "# P\n\nBe concise and prefer small pull requests.\n"
    )
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "y.md").write_text(
        "## Deploy\n\nTag releases with semver and never deploy on Friday.\n"
    )
    return tmp_path


# ---- recommended_optimize_command: 단일 진실 공급원 ----------------------


def test_recommended_command_for_chunk_only_is_level3(tmp_path):
    sources, _ = run_inventory(_chunk_dup_project(tmp_path))
    assert recommended_optimize_command(sources) == "rune optimize --level 3 --dry-run"


def test_recommended_command_for_exact_dup_is_level1(tmp_path):
    sources, _ = run_inventory(_exact_dup_project(tmp_path))
    assert recommended_optimize_command(sources) == "rune optimize --dry-run"


def test_recommended_command_none_when_no_duplicate(tmp_path):
    sources, _ = run_inventory(_no_dup_project(tmp_path))
    assert recommended_optimize_command(sources) is None


# ---- analyze 추천 명령이 JSON 으로 노출되고 신호에 맞다 ------------------


def test_analyze_json_recommends_level3_for_chunk_only(tmp_path):
    result = runner.invoke(app, ["analyze", "--json", str(_chunk_dup_project(tmp_path))])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommend_optimize"] is True
    assert data["optimize_command"] == "rune optimize --level 3 --dry-run"


def test_analyze_json_no_command_when_no_duplicate(tmp_path):
    result = runner.invoke(app, ["analyze", "--json", str(_no_dup_project(tmp_path))])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommend_optimize"] is False
    assert data["optimize_command"] is None


def test_analyze_text_report_shows_level3_command(tmp_path):
    result = runner.invoke(app, ["analyze", str(_chunk_dup_project(tmp_path))])
    assert result.exit_code == 0
    assert "rune optimize --level 3 --dry-run" in _plain(result.stdout)


# ---- 핵심: 추천한 명령을 그대로 실행하면 실제 절약 ----------------------


def test_recommended_command_realizes_actual_savings(tmp_path):
    """analyze 가 추천한 level 3 dry-run 을 그대로 실행하면 0 이 아닌 절약을 본다."""
    target = _chunk_dup_project(tmp_path)
    analyze = runner.invoke(app, ["analyze", "--json", str(target)])
    cmd = json.loads(analyze.stdout)["optimize_command"]
    assert cmd == "rune optimize --level 3 --dry-run"

    # 추천 명령 그대로 실행
    opt = runner.invoke(app, ["optimize", "--level", "3", "--dry-run", str(target)])
    assert opt.exit_code == 0
    assert "예상 절약" in opt.stdout
    # 0 절약이 아니어야 한다.
    assert "예상 절약: [green]0[/green]" not in opt.stdout
    assert "0 tokens" not in opt.stdout or "예상 절약: 0" not in opt.stdout


def test_level3_apply_realizes_nonzero_savings(tmp_path):
    """실제 적용(dry-run 아님) 시 청크 병합으로 실제 토큰을 절약한다."""
    target = _chunk_dup_project(tmp_path)
    opt = runner.invoke(app, ["optimize", "--level", "3", str(target)])
    assert opt.exit_code == 0
    assert "완료" in opt.stdout
    # 청크 병합이 실제로 일어났으므로 절약 0 + 완료 조합이 아니어야 한다.
    assert "절약: 0 tokens" not in opt.stdout


# ---- 핵심: 기본 level 1 이 청크 중복에 거짓 "완료 0" 보고를 하지 않는다 --


def test_level1_does_not_falsely_report_complete_with_zero(tmp_path):
    """청크 중복만 있는데 기본 optimize(level 1) 실행 시
    '완료 — 절약: 0 tokens' 거짓 보고를 하지 않고 정확한 다음 단계를 안내한다."""
    target = _chunk_dup_project(tmp_path)
    opt = runner.invoke(app, ["optimize", str(target)])
    assert opt.exit_code == 0
    out = _plain(opt.stdout)
    # 거짓 "완료 + 0 절약" 조합 금지
    assert "완료" not in out
    assert "절약: 0 tokens" not in out
    # 정확한 다음 단계 안내
    assert "rune optimize --level 3 --dry-run" in out


def test_level1_exact_dup_still_reports_complete_with_savings(tmp_path, monkeypatch):
    """완전 동일 파일은 level 1 이 실제로 병합하므로 '완료' + 0 이 아닌 절약.

    백업 경로는 cwd 기준 상대 경로로 계산되므로 target 을 cwd 로 둔다.
    """
    target = _exact_dup_project(tmp_path)
    monkeypatch.chdir(target)
    opt = runner.invoke(app, ["optimize"])
    assert opt.exit_code == 0
    out = _plain(opt.stdout)
    assert "완료" in out
    assert "절약: 0 tokens" not in out


# ---- 중복 없는 디렉토리: 추천 안 함 + optimize "대상 없음" 정합 --------


def test_no_duplicate_dir_no_recommend_and_no_target(tmp_path):
    target = _no_dup_project(tmp_path)
    analyze = runner.invoke(app, ["analyze", "--json", str(target)])
    assert json.loads(analyze.stdout)["recommend_optimize"] is False

    opt = runner.invoke(app, ["optimize", "--dry-run", str(target)])
    assert opt.exit_code == 0
    assert "최적화 대상 없음" in opt.stdout
