"""v0.3 서브청크(규칙 라인) 단위 중복 탐지 테스트.

검증 항목:
  (a) 동일 규칙이 두 파일의 서로 다른 문단에 섞여 있어도 규칙 단위 중복으로 탐지.
  (b) 무중복 파일 쌍에서 false-positive 없음.
  (c) analyze --json 출력에 schema_version 필드 존재.
  (d) 기존 청크/파일 단위 dedup 회귀 없음.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rune.models.source import Chunk, InjectionSource
from rune.pipeline.dedup import (
    find_dedup_rule_pairs,
    find_dedup_pairs,
    find_dedup_chunk_pairs,
    RuleDedupPair,
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_source(path: str, text: str, start_line: int = 1) -> InjectionSource:
    """단일 청크를 가진 InjectionSource 를 생성한다."""
    lines = text.splitlines()
    end_line = start_line + max(len(lines) - 1, 0)
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=None,
        chunks=[
            Chunk(
                text=text,
                start_line=start_line,
                end_line=end_line,
                token_count=len(text.split()),
            )
        ],
    )


def _make_source_multi(path: str, chunks_text: list[str]) -> InjectionSource:
    """복수 청크를 가진 InjectionSource 를 생성한다."""
    chunks = []
    line = 1
    for text in chunks_text:
        lines = text.splitlines()
        end = line + max(len(lines) - 1, 0)
        chunks.append(Chunk(text=text, start_line=line, end_line=end, token_count=len(text.split())))
        line = end + 2  # 빈 줄 하나 간격
    return InjectionSource(path=Path(path), source_type="rule", trigger=None, chunks=chunks)


# ---------------------------------------------------------------------------
# (a) 서로 다른 문단에 섞인 동일 규칙 탐지
# ---------------------------------------------------------------------------

RULE_UNIT_TEST = "- Always write unit tests before shipping any feature code."

# 파일 A: 코딩 규칙 문단 + 문서 규칙 문단. 규칙 라인이 첫 번째 문단에 포함.
FILE_A_CHUNK1 = """\
## 코딩 규칙
- Always write unit tests before shipping any feature code.
- Use type hints in all public APIs.
"""

FILE_A_CHUNK2 = """\
## 문서 규칙
- Keep README up to date.
- Changelog entries are required for every release.
"""

# 파일 B: 완전히 다른 구조. 규칙 라인이 두 번째 문단에 포함.
FILE_B_CHUNK1 = """\
## 배포 규칙
- Run CI pipeline before merging any pull request.
- Require two approvals for production deploys.
"""

FILE_B_CHUNK2 = """\
## 품질 규칙
- Always write unit tests before shipping any feature code.
- Measure code coverage and maintain above 80 percent.
"""


def test_rule_detected_across_different_chunks():
    """(a) 같은 규칙 라인이 서로 다른 문단에 섞여 있어도 rule pair 로 탐지된다."""
    src_a = _make_source_multi("rules/coding.md", [FILE_A_CHUNK1, FILE_A_CHUNK2])
    src_b = _make_source_multi("rules/quality.md", [FILE_B_CHUNK1, FILE_B_CHUNK2])

    pairs = find_dedup_rule_pairs([src_a, src_b])
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]

    # 적어도 해당 규칙 라인이 탐지되어야 한다.
    assert len(high_pairs) >= 1, "서로 다른 문단의 동일 규칙이 탐지되지 않았음"

    # 탐지된 쌍의 텍스트에 "unit tests" 가 포함되어야 한다.
    found_rule = any(
        "unit tests" in p.text.lower() for p in high_pairs
    )
    assert found_rule, f"'unit tests' 규칙이 탐지 결과에 없음: {[p.text for p in high_pairs]}"


def test_rule_pairs_return_type():
    """find_dedup_rule_pairs 가 RuleDedupPair 목록을 반환한다."""
    src_a = _make_source("a.md", "- Always write unit tests.\n")
    src_b = _make_source("b.md", "- Always write unit tests.\n")
    pairs = find_dedup_rule_pairs([src_a, src_b])
    for p in pairs:
        assert isinstance(p, RuleDedupPair)


# ---------------------------------------------------------------------------
# (b) false-positive 없음
# ---------------------------------------------------------------------------

def test_no_false_positive_unrelated_rules():
    """(b) 완전히 다른 규칙 라인을 가진 파일 쌍에서 HIGH 중복이 없어야 한다."""
    src_a = _make_source(
        "rules/git.md",
        "- Never force push to main branch.\n- Always rebase before merging.\n",
    )
    src_b = _make_source(
        "rules/python.md",
        "- Use type hints in all public functions.\n- Format code with black.\n",
    )
    pairs = find_dedup_rule_pairs([src_a, src_b])
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]
    assert len(high_pairs) == 0, f"관련 없는 규칙에서 false-positive 발생: {high_pairs}"


def test_no_false_positive_empty_sources():
    """빈 목록은 빈 결과를 반환한다."""
    assert find_dedup_rule_pairs([]) == []


def test_no_false_positive_single_source():
    """소스가 하나뿐이면 빈 결과를 반환한다."""
    src = _make_source("rules/only.md", "- Write tests.\n- Use type hints.\n")
    assert find_dedup_rule_pairs([src]) == []


def test_same_file_lines_not_reported():
    """같은 파일 내 동일 라인은 파일 간 비교가 아니므로 포함되지 않아야 한다."""
    # 같은 규칙이 두 번 등장하는 단일 파일
    src = _make_source(
        "rules/dup_internal.md",
        "- Always write unit tests.\n- Always write unit tests.\n",
    )
    src_other = _make_source("rules/unrelated.md", "- Keep docs updated.\n")
    pairs = find_dedup_rule_pairs([src, src_other])
    # src 내부 쌍(같은 파일)은 결과에 없어야 한다.
    same_file_pairs = [p for p in pairs if p.source_a == p.source_b]
    assert len(same_file_pairs) == 0


# ---------------------------------------------------------------------------
# (c) schema_version 존재
# ---------------------------------------------------------------------------

def test_analyze_json_schema_version(tmp_path):
    """(c) analyze --json 출력에 schema_version 필드가 존재하고 값이 '1.1' 이다."""
    from typer.testing import CliRunner
    from rune.cli.main import app

    # 최소한의 CLAUDE.md 파일 생성
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "# Rules\n- Always write unit tests.\n- Use type hints.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(tmp_path), "--json", "--no-semantic"])
    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"

    data = json.loads(result.output)
    assert "schema_version" in data, f"schema_version 필드 없음: {data.keys()}"
    assert data["schema_version"] == "1.1"


def test_analyze_json_has_dedup_rule_high(tmp_path):
    """analyze --json 출력에 dedup_rule_high 필드가 존재한다."""
    from typer.testing import CliRunner
    from rune.cli.main import app

    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Rules\n- Always write unit tests.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["analyze", str(tmp_path), "--json", "--no-semantic"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert "dedup_rule_high" in data, f"dedup_rule_high 필드 없음: {data.keys()}"
    assert isinstance(data["dedup_rule_high"], int)


# ---------------------------------------------------------------------------
# (d) 기존 청크/파일 단위 dedup 회귀 없음
# ---------------------------------------------------------------------------

def test_find_dedup_pairs_regression():
    """(d) 기존 find_dedup_pairs 가 동일 소스를 HIGH confidence 로 탐지한다."""
    text = "Never force push main. Always run tests before deploy."
    s1 = _make_source("rules/git.md", text)
    s2 = _make_source("rules/duplicate.md", text)
    pairs = find_dedup_pairs([s1, s2])
    assert len(pairs) >= 1
    assert pairs[0].confidence == "HIGH"


def test_find_dedup_pairs_different_sources():
    """(d) 다른 내용의 소스 쌍은 HIGH confidence 가 없다."""
    s1 = _make_source("rules/git.md", "Git rules: never force push main branch.")
    s2 = _make_source("rules/python.md", "Python rules: use type hints and write tests.")
    pairs = find_dedup_pairs([s1, s2])
    high = [p for p in pairs if p.confidence == "HIGH"]
    assert len(high) == 0


def test_find_dedup_chunk_pairs_regression():
    """(d) 기존 find_dedup_chunk_pairs 가 동일 청크를 HIGH confidence 로 탐지한다."""
    text = "Always run the full test suite before merging any pull request to main."
    s1 = _make_source("rules/ci.md", text)
    s2 = _make_source("rules/ci_dup.md", text)
    pairs = find_dedup_chunk_pairs([s1, s2])
    high = [p for p in pairs if p.confidence == "HIGH"]
    assert len(high) >= 1


def test_min_chars_filter():
    """16자 미만 규칙 라인은 서브청크 비교에서 제외된다."""
    src_a = _make_source("a.md", "- Short.\n- Always write unit tests before shipping features.\n")
    src_b = _make_source("b.md", "- Short.\n- Always write unit tests before shipping features.\n")
    pairs = find_dedup_rule_pairs([src_a, src_b])
    # "Short." 은 16자 미만이므로 필터되어야 하며, unit tests 규칙만 탐지
    texts = [p.text for p in pairs if p.confidence == "HIGH"]
    short_detected = any("Short" in t for t in texts)
    assert not short_detected, f"짧은 라인이 잘못 탐지됨: {texts}"


def test_max_pairs_limit():
    """쌍 수 상한(_MAX_RULE_PAIRS=500) 을 초과하지 않는다."""
    from rune.pipeline.dedup import _MAX_RULE_PAIRS

    # 각 파일에 동일 규칙 라인을 여러 개 포함
    lines_a = "\n".join(f"- Rule number {i:03d} that is always required to follow." for i in range(50))
    lines_b = "\n".join(f"- Rule number {i:03d} that is always required to follow." for i in range(50))
    src_a = _make_source("rules/many_a.md", lines_a)
    src_b = _make_source("rules/many_b.md", lines_b)
    pairs = find_dedup_rule_pairs([src_a, src_b])
    assert len(pairs) <= _MAX_RULE_PAIRS
