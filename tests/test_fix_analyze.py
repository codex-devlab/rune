"""[중간-6]/[중간-7] 회귀 테스트.

- analyze 추천 조건과 optimize 실제 동작 조건의 정합화
- 청크(규칙) 단위 중복 탐지
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from rune.cli.main import app
from rune.models.source import Chunk, InjectionSource
from rune.pipeline.dedup import find_dedup_pairs, find_dedup_chunk_pairs
from rune.cli.optimize import has_optimization_targets, find_optimization_targets

runner = CliRunner()


def _make_source(path: str, paragraphs: list[str]) -> InjectionSource:
    chunks = [
        Chunk(text=p, start_line=1, end_line=1, token_count=len(p.split()))
        for p in paragraphs
    ]
    return InjectionSource(path=Path(path), source_type="rule", trigger=None, chunks=chunks)


def _tdd_project(tmp_path: Path) -> Path:
    """CLAUDE.md 와 .claude/rules/x.md 양쪽에 동일한 'Always use TDD' 규칙."""
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


# ---- [중간-7] 청크 단위 중복 탐지 ----------------------------------------


def test_chunk_pairs_detect_cross_file_duplicate_rule():
    tdd = "Always use TDD. Write a failing test first, then refactor afterwards."
    s1 = _make_source("CLAUDE.md", [tdd, "Be concise in reviews and keep PRs small."])
    s2 = _make_source(".claude/rules/x.md", [tdd, "Keep tests beside the code."])
    chunk_pairs = find_dedup_chunk_pairs([s1, s2])
    high = [p for p in chunk_pairs if p.confidence == "HIGH"]
    assert len(high) >= 1
    # 중복 청크의 경로가 서로 다른 파일에 걸쳐 있어야 한다.
    p = high[0]
    assert {str(p.source_a), str(p.source_b)} == {"CLAUDE.md", ".claude/rules/x.md"}


def test_file_level_misses_what_chunk_level_catches():
    """파일 전체가 다르면 파일단위 비교는 HIGH 를 못 잡지만 청크단위는 잡는다."""
    tdd = "Always use TDD. Write a failing test first, then refactor afterwards."
    s1 = _make_source(
        "CLAUDE.md",
        [tdd, "Unique paragraph about deployment cadence and release tagging only."],
    )
    s2 = _make_source(
        ".claude/rules/x.md",
        [tdd, "Totally different content discussing security secrets and rotations."],
    )
    file_high = [p for p in find_dedup_pairs([s1, s2]) if p.confidence == "HIGH"]
    chunk_high = [p for p in find_dedup_chunk_pairs([s1, s2]) if p.confidence == "HIGH"]
    assert len(file_high) == 0
    assert len(chunk_high) >= 1


def test_chunk_pairs_ignore_short_noise():
    s1 = _make_source("a.md", ["ok", "ok"])
    s2 = _make_source("b.md", ["ok"])
    assert find_dedup_chunk_pairs([s1, s2]) == []


def test_chunk_pairs_no_false_positive_for_distinct_rules():
    s1 = _make_source("a.md", ["Never force push to the main branch under any circumstances."])
    s2 = _make_source("b.md", ["Always add type hints to every public function signature."])
    high = [p for p in find_dedup_chunk_pairs([s1, s2]) if p.confidence == "HIGH"]
    assert len(high) == 0


# ---- [중간-6] analyze 추천 ↔ optimize 결과 정합 ---------------------------


def test_has_optimization_targets_true_when_chunk_duplicate(tmp_path):
    from rune.pipeline.inventory import run_inventory

    sources, _ = run_inventory(_tdd_project(tmp_path))
    assert has_optimization_targets(sources) is True


def test_has_optimization_targets_false_when_no_duplicate(tmp_path):
    from rune.pipeline.inventory import run_inventory

    (tmp_path / "CLAUDE.md").write_text("# P\n\nBe concise and prefer small pull requests.\n")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "y.md").write_text("## Deploy\n\nTag releases with semver and never deploy on Friday.\n")
    sources, _ = run_inventory(tmp_path)
    assert has_optimization_targets(sources) is False


def test_analyze_recommends_optimize_when_chunk_duplicate(tmp_path):
    result = runner.invoke(app, ["analyze", "--json", str(_tdd_project(tmp_path))])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dedup_chunk_high"] >= 1
    assert data["recommend_optimize"] is True


def test_analyze_does_not_recommend_without_duplicate(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nBe concise and prefer small pull requests.\n")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "y.md").write_text("## Deploy\n\nTag releases with semver and never deploy on Friday.\n")
    result = runner.invoke(app, ["analyze", "--json", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommend_optimize"] is False


def test_optimize_dry_run_has_target_when_analyze_recommends(tmp_path):
    """추천-결과 정합: analyze 추천 시 optimize --dry-run 이 실제 대상을 보여줘야 한다."""
    target = _tdd_project(tmp_path)
    analyze = runner.invoke(app, ["analyze", "--json", str(target)])
    assert json.loads(analyze.stdout)["recommend_optimize"] is True

    opt = runner.invoke(app, ["optimize", "--dry-run", str(target)])
    assert opt.exit_code == 0
    assert "최적화 대상 없음" not in opt.stdout
    assert "청크" in opt.stdout


def test_optimize_dry_run_no_target_when_no_duplicate(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# P\n\nBe concise and prefer small pull requests.\n")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "y.md").write_text("## Deploy\n\nTag releases with semver and never deploy on Friday.\n")
    opt = runner.invoke(app, ["optimize", "--dry-run", str(tmp_path)])
    assert opt.exit_code == 0
    assert "최적화 대상 없음" in opt.stdout


def test_optimize_level3_realizes_chunk_savings(tmp_path):
    target = _tdd_project(tmp_path)
    opt = runner.invoke(app, ["optimize", "--level", "3", "--dry-run", str(target)])
    assert opt.exit_code == 0
    assert "예상 절약" in opt.stdout
