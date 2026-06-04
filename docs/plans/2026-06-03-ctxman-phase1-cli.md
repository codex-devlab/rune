# ctxman Phase 1 CLI MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `ctxman analyze` CLI that measures static token injection waste across LLM agent config files, works on empty projects without crashing, and reports level-appropriate output.

**Architecture:** Platform adapter detects project type (Claude Code/Cursor/Copilot/Generic), feeds 5-stage pipeline (Inventory→Tokenize→Score→Dedup→Trigger), outputs level-aware report. All adapters return `[]` on missing files — never raise.

**Tech Stack:** Python 3.11+, typer, tiktoken, scikit-learn, sentence-transformers, pytest

---

## File Map

```
/Users/codex/Workspace/ToolSet/app/
├── pyproject.toml                       ← project metadata + dependencies
├── README.md                            ← user-facing docs
├── ctxman/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                      ← typer app entry point
│   │   ├── analyze.py                   ← ctxman analyze command
│   │   ├── init_cmd.py                  ← ctxman init command
│   │   ├── scaffold.py                  ← ctxman scaffold command
│   │   └── watch.py                     ← ctxman watch command
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py                      ← InjectionAdapter ABC + Platform enum
│   │   ├── claude_code.py               ← CLAUDE.md, .claude/rules/, skills/
│   │   ├── cursor.py                    ← .cursorrules, .cursor/
│   │   └── generic.py                   ← *.md scan + empty project fallback
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── inventory.py                 ← Stage 1: detect + list sources
│   │   ├── tokenizer.py                 ← Stage 2: token counting
│   │   ├── scorer.py                    ← Stage 3: Tier1(structural)+Tier2(TF-IDF)
│   │   ├── dedup.py                     ← Stage 4: cosine similarity dedup
│   │   └── trigger.py                   ← Stage 5: keyword extraction
│   ├── models/
│   │   ├── __init__.py
│   │   ├── source.py                    ← InjectionSource, Chunk dataclasses
│   │   └── report.py                    ← AnalysisReport, DedupPair, TriggerResult
│   └── scaffold/
│       ├── __init__.py
│       ├── generator.py                 ← template file generation
│       └── templates/
│           ├── claude-code-base/
│           │   ├── CLAUDE.md
│           │   └── rules/git.md
│           └── python-backend/
│               ├── CLAUDE.md
│               └── rules/python.md
└── tests/
    ├── conftest.py                      ← shared fixtures (tmp project dirs)
    ├── test_adapters.py
    ├── test_tokenizer.py
    ├── test_scorer.py
    ├── test_dedup.py
    ├── test_trigger.py
    ├── test_cli.py
    └── test_e2e.py                      ← Benchmark-0 through Benchmark-2
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `ctxman/__init__.py`
- Create: `ctxman/cli/__init__.py`
- Create: `ctxman/adapters/__init__.py`
- Create: `ctxman/pipeline/__init__.py`
- Create: `ctxman/models/__init__.py`
- Create: `ctxman/scaffold/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "ctxman"
version = "0.1.0"
description = "Static Instruction Injection Optimizer for LLM agents"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "tiktoken>=0.7",
    "scikit-learn>=1.4",
    "sentence-transformers>=3.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-tmp-files>=0.1"]

[project.scripts]
ctxman = "ctxman.cli.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `__init__.py` files**

```bash
mkdir -p ctxman/cli ctxman/adapters ctxman/pipeline ctxman/models ctxman/scaffold tests
touch ctxman/__init__.py ctxman/cli/__init__.py ctxman/adapters/__init__.py
touch ctxman/pipeline/__init__.py ctxman/models/__init__.py ctxman/scaffold/__init__.py
touch tests/__init__.py
```

- [ ] **Step 3: Create tests/conftest.py**

```python
import pytest
from pathlib import Path


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """Benchmark-0: completely empty directory."""
    return tmp_path


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """Benchmark-1: single CLAUDE.md, no rules."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\nBe concise. Write tests first.\n"
    )
    return tmp_path


@pytest.fixture
def complex_project(tmp_path: Path) -> Path:
    """Benchmark-2: CLAUDE.md + multiple rules (pmo-vault-like)."""
    (tmp_path / "CLAUDE.md").write_text("# PMO Vault\n\nCore rules apply.\n")
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    rule_texts = {
        "git.md": "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push main.",
        "python.md": "## Python Rules\n\nTrigger: python, pytest\n\nUse type hints always.",
        "deploy.md": "## Deploy Rules\n\nTrigger: deploy, production\n\nRun tests before deploy.",
        "docs.md": "## Docs Rules\n\nTrigger: docs, readme\n\nKeep README updated.",
        "security.md": "## Security Rules\n\nTrigger: auth, secret, password\n\nNever commit secrets.",
        "duplicate.md": "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push main.",
    }
    for name, content in rule_texts.items():
        (rules_dir / name).write_text(content)
    return tmp_path
```

- [ ] **Step 4: Install dependencies and verify**

```bash
cd /Users/codex/Workspace/ToolSet/app
pip install -e ".[dev]"
python -c "import ctxman; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml ctxman/ tests/conftest.py
git commit -m "feat(ctxman): project scaffold and test fixtures"
```

---

## Task 2: Data Models

**Files:**
- Create: `ctxman/models/source.py`
- Create: `ctxman/models/report.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_models.py`:

```python
from ctxman.models.source import Chunk, InjectionSource
from ctxman.models.report import AnalysisReport, DedupPair, TriggerResult
from pathlib import Path


def test_chunk_token_count():
    chunk = Chunk(text="hello world", start_line=1, end_line=1, token_count=2)
    assert chunk.token_count == 2


def test_injection_source_total_tokens():
    chunks = [
        Chunk(text="a", start_line=1, end_line=1, token_count=10),
        Chunk(text="b", start_line=2, end_line=2, token_count=5),
    ]
    source = InjectionSource(
        path=Path("rules/git.md"),
        source_type="rule",
        trigger=None,
        chunks=chunks,
    )
    assert source.token_count == 15


def test_dedup_pair_confidence():
    pair = DedupPair(
        source_a=Path("a.md"),
        source_b=Path("b.md"),
        similarity=0.95,
        confidence="HIGH",
    )
    assert pair.confidence == "HIGH"


def test_analysis_report_level():
    report = AnalysisReport(
        total_tokens=0,
        sources=[],
        dedup_pairs=[],
        trigger_results=[],
        level=0,
    )
    assert report.level == 0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create ctxman/models/source.py**

```python
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    text: str
    start_line: int
    end_line: int
    token_count: int
    importance_score: float = 0.0


@dataclass
class InjectionSource:
    path: Path
    source_type: str  # "claude_md" | "rule" | "memory" | "skill"
    trigger: str | None
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        return sum(c.token_count for c in self.chunks)
```

- [ ] **Step 4: Create ctxman/models/report.py**

```python
from dataclasses import dataclass, field
from pathlib import Path
from ctxman.models.source import InjectionSource


@dataclass
class DedupPair:
    source_a: Path
    source_b: Path
    similarity: float
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"


@dataclass
class TriggerResult:
    source: Path
    keywords: list[str]
    method: str  # "parsed" | "tfidf"


@dataclass
class AnalysisReport:
    total_tokens: int
    sources: list[InjectionSource]
    dedup_pairs: list[DedupPair]
    trigger_results: list[TriggerResult]
    level: int  # 0-3
    estimated_savings: int = 0
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_models.py -v
```

Expected: 4 tests PASS

```bash
git add ctxman/models/ tests/test_models.py
git commit -m "feat(ctxman): data models (InjectionSource, Chunk, AnalysisReport)"
```

---

## Task 3: Platform Detection + Adapter Interface

**Files:**
- Create: `ctxman/adapters/base.py`
- Test: `tests/test_adapters.py` (partial)

- [ ] **Step 1: Write failing tests for platform detection**

Create `tests/test_adapters.py`:

```python
import pytest
from pathlib import Path
from ctxman.adapters.base import Platform, detect_platform


def test_detect_claude_code_by_dot_claude(tmp_path):
    (tmp_path / ".claude").mkdir()
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE


def test_detect_claude_code_by_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# test")
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE


def test_detect_cursor(tmp_path):
    (tmp_path / ".cursor").mkdir()
    assert detect_platform(tmp_path) == Platform.CURSOR


def test_detect_cursor_by_rules_file(tmp_path):
    (tmp_path / ".cursorrules").write_text("# cursor rules")
    assert detect_platform(tmp_path) == Platform.CURSOR


def test_detect_generic_on_empty(tmp_path):
    assert detect_platform(tmp_path) == Platform.GENERIC


def test_claude_code_takes_priority_over_cursor(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    assert detect_platform(tmp_path) == Platform.CLAUDE_CODE
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_adapters.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/adapters/base.py**

```python
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from ctxman.models.source import InjectionSource


class Platform(str, Enum):
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    COPILOT = "copilot"
    GENERIC = "generic"


def detect_platform(path: Path) -> Platform:
    if (path / ".claude").exists():
        return Platform.CLAUDE_CODE
    if (path / ".cursor").exists():
        return Platform.CURSOR
    if (path / ".github" / "copilot").exists():
        return Platform.COPILOT
    if any(path.glob("CLAUDE.md")):
        return Platform.CLAUDE_CODE
    if any(path.glob(".cursorrules")):
        return Platform.CURSOR
    return Platform.GENERIC


class InjectionAdapter(ABC):
    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this adapter handles the given project path."""

    @abstractmethod
    def list_sources(self, path: Path) -> list[InjectionSource]:
        """Return all injection sources. MUST return [] on missing files, never raise."""
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_adapters.py -v
```

Expected: 6 tests PASS

```bash
git add ctxman/adapters/base.py tests/test_adapters.py
git commit -m "feat(ctxman): platform auto-detection and adapter interface"
```

---

## Task 4: Tokenizer

**Files:**
- Create: `ctxman/pipeline/tokenizer.py`
- Test: `tests/test_tokenizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tokenizer.py`:

```python
from pathlib import Path
from ctxman.pipeline.tokenizer import count_tokens, split_into_chunks


def test_count_tokens_returns_int():
    n = count_tokens("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_split_into_chunks_non_empty():
    text = "# Header\n\nFirst paragraph.\n\n# Header 2\n\nSecond paragraph.\n"
    chunks = split_into_chunks(text)
    assert len(chunks) >= 2
    assert all(c.token_count > 0 for c in chunks)


def test_split_into_chunks_empty_text():
    chunks = split_into_chunks("")
    assert chunks == []


def test_chunks_cover_full_text(tmp_path):
    text = "line1\nline2\nline3\n"
    chunks = split_into_chunks(text)
    combined = " ".join(c.text for c in chunks)
    assert "line1" in combined
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_tokenizer.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/pipeline/tokenizer.py**

```python
from ctxman.models.source import Chunk

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except ImportError:
    def count_tokens(text: str) -> int:
        # fallback: ~4 chars per token (±10% accuracy)
        return max(0, len(text) // 4)


def split_into_chunks(text: str) -> list[Chunk]:
    """Split text on blank lines into paragraph chunks."""
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[Chunk] = []
    current_line = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            current_line += 2
            continue
        line_count = para.count("\n") + 1
        token_count = count_tokens(para)
        chunks.append(
            Chunk(
                text=para,
                start_line=current_line,
                end_line=current_line + line_count - 1,
                token_count=token_count,
            )
        )
        current_line += line_count + 1  # +1 for blank line separator

    return chunks
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_tokenizer.py -v
```

Expected: 5 tests PASS

```bash
git add ctxman/pipeline/tokenizer.py tests/test_tokenizer.py
git commit -m "feat(ctxman): tokenizer with tiktoken and char-count fallback"
```

---

## Task 5: Claude Code Adapter

**Files:**
- Create: `ctxman/adapters/claude_code.py`
- Modify: `tests/test_adapters.py` (add ClaudeCodeAdapter tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_adapters.py`:

```python
from ctxman.adapters.claude_code import ClaudeCodeAdapter


def test_claude_code_adapter_empty_project(empty_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(empty_project)
    assert sources == []  # no crash on empty dir


def test_claude_code_adapter_finds_claude_md(minimal_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(minimal_project)
    types = [s.source_type for s in sources]
    assert "claude_md" in types


def test_claude_code_adapter_finds_rules(complex_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(complex_project)
    rule_sources = [s for s in sources if s.source_type == "rule"]
    assert len(rule_sources) >= 5


def test_claude_code_adapter_sources_have_tokens(complex_project):
    adapter = ClaudeCodeAdapter()
    sources = adapter.list_sources(complex_project)
    assert all(s.token_count > 0 for s in sources)


def test_claude_code_adapter_detect(tmp_path):
    (tmp_path / ".claude").mkdir()
    adapter = ClaudeCodeAdapter()
    assert adapter.detect(tmp_path) is True


def test_claude_code_adapter_detect_false(tmp_path):
    adapter = ClaudeCodeAdapter()
    assert adapter.detect(tmp_path) is False
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_adapters.py::test_claude_code_adapter_empty_project -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/adapters/claude_code.py**

```python
from pathlib import Path
from ctxman.adapters.base import InjectionAdapter
from ctxman.models.source import InjectionSource
from ctxman.pipeline.tokenizer import split_into_chunks


class ClaudeCodeAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".claude").exists() or (path / "CLAUDE.md").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        # CLAUDE.md files (root and subdirectories)
        for md_file in sorted(path.glob("**/CLAUDE.md")):
            sources.append(self._read_source(md_file, "claude_md"))

        # .claude/rules/
        rules_dir = path / ".claude" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.glob("**/*.md")):
                sources.append(self._read_source(rule_file, "rule"))

        # .claude/skills/
        skills_dir = path / ".claude" / "skills"
        if skills_dir.exists():
            for skill_file in sorted(skills_dir.glob("**/SKILL.md")):
                sources.append(self._read_source(skill_file, "skill"))

        return sources

    def _read_source(self, path: Path, source_type: str) -> InjectionSource:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        chunks = split_into_chunks(text)
        trigger = self._extract_trigger(text)
        return InjectionSource(
            path=path,
            source_type=source_type,
            trigger=trigger,
            chunks=chunks,
        )

    def _extract_trigger(self, text: str) -> str | None:
        """Extract first trigger keyword line if present."""
        for line in text.splitlines():
            lower = line.lower().strip()
            if lower.startswith("trigger:") or lower.startswith("트리거:"):
                return line.split(":", 1)[-1].strip()
        return None
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_adapters.py -v
```

Expected: all adapter tests PASS

```bash
git add ctxman/adapters/claude_code.py tests/test_adapters.py
git commit -m "feat(ctxman): Claude Code adapter (CLAUDE.md, rules, skills)"
```

---

## Task 6: Generic Adapter + Cursor Adapter

**Files:**
- Create: `ctxman/adapters/generic.py`
- Create: `ctxman/adapters/cursor.py`
- Modify: `tests/test_adapters.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_adapters.py`:

```python
from ctxman.adapters.generic import GenericAdapter
from ctxman.adapters.cursor import CursorAdapter


def test_generic_adapter_empty_project_no_crash(empty_project):
    adapter = GenericAdapter()
    sources = adapter.list_sources(empty_project)
    assert isinstance(sources, list)  # [] is fine


def test_generic_adapter_finds_md_files(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Agent rules\n\nBe helpful.")
    adapter = GenericAdapter()
    sources = adapter.list_sources(tmp_path)
    assert len(sources) >= 1


def test_cursor_adapter_empty_no_crash(empty_project):
    adapter = CursorAdapter()
    sources = adapter.list_sources(empty_project)
    assert sources == []


def test_cursor_adapter_finds_cursorrules(tmp_path):
    (tmp_path / ".cursorrules").write_text("Always use TypeScript strict mode.")
    adapter = CursorAdapter()
    sources = adapter.list_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_type == "cursor_rules"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_adapters.py -k "generic or cursor" -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/adapters/generic.py**

```python
from pathlib import Path
from ctxman.adapters.base import InjectionAdapter
from ctxman.models.source import InjectionSource
from ctxman.pipeline.tokenizer import split_into_chunks

_SKIP_DIRS = {".git", ".repo", "node_modules", "__pycache__", ".venv", "venv"}
_AGENT_MD_NAMES = {"CLAUDE.md", "AGENTS.md", "GEMINI.md", "COPILOT.md"}


class GenericAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return True  # always available as fallback

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []
        for md_file in self._walk_md(path):
            text = self._safe_read(md_file)
            chunks = split_into_chunks(text)
            sources.append(
                InjectionSource(
                    path=md_file,
                    source_type="generic_md",
                    trigger=None,
                    chunks=chunks,
                )
            )
        return sources

    def _walk_md(self, path: Path):
        for item in path.rglob("*.md"):
            if any(skip in item.parts for skip in _SKIP_DIRS):
                continue
            if item.name in _AGENT_MD_NAMES:
                yield item

    def _safe_read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
```

- [ ] **Step 4: Create ctxman/adapters/cursor.py**

```python
from pathlib import Path
from ctxman.adapters.base import InjectionAdapter
from ctxman.models.source import InjectionSource
from ctxman.pipeline.tokenizer import split_into_chunks


class CursorAdapter(InjectionAdapter):
    def detect(self, path: Path) -> bool:
        return (path / ".cursor").exists() or (path / ".cursorrules").exists()

    def list_sources(self, path: Path) -> list[InjectionSource]:
        sources: list[InjectionSource] = []

        rules_file = path / ".cursorrules"
        if rules_file.exists():
            sources.append(self._read(rules_file, "cursor_rules"))

        cursor_dir = path / ".cursor" / "rules"
        if cursor_dir.exists():
            for f in sorted(cursor_dir.glob("**/*.md")):
                sources.append(self._read(f, "cursor_rule"))

        return sources

    def _read(self, path: Path, source_type: str) -> InjectionSource:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        return InjectionSource(
            path=path,
            source_type=source_type,
            trigger=None,
            chunks=split_into_chunks(text),
        )
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_adapters.py -v
```

Expected: all adapter tests PASS

```bash
git add ctxman/adapters/generic.py ctxman/adapters/cursor.py tests/test_adapters.py
git commit -m "feat(ctxman): generic and cursor adapters"
```

---

## Task 7: Pipeline — INVENTORY

**Files:**
- Create: `ctxman/pipeline/inventory.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pipeline.py`:

```python
import pytest
from pathlib import Path
from ctxman.pipeline.inventory import run_inventory
from ctxman.adapters.base import Platform


def test_inventory_empty_project(empty_project):
    sources, platform = run_inventory(empty_project)
    assert sources == []
    assert platform == Platform.GENERIC


def test_inventory_minimal_project(minimal_project):
    sources, platform = run_inventory(minimal_project)
    assert platform == Platform.CLAUDE_CODE
    assert len(sources) >= 1


def test_inventory_complex_project(complex_project):
    sources, platform = run_inventory(complex_project)
    assert platform == Platform.CLAUDE_CODE
    assert len(sources) >= 6  # CLAUDE.md + 6 rules


def test_inventory_never_raises(tmp_path):
    # Simulate permission denied by passing non-existent nested path
    sources, platform = run_inventory(tmp_path / "does_not_exist")
    assert isinstance(sources, list)
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_pipeline.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/pipeline/inventory.py**

```python
from pathlib import Path
from ctxman.adapters.base import Platform, detect_platform, InjectionAdapter
from ctxman.adapters.claude_code import ClaudeCodeAdapter
from ctxman.adapters.cursor import CursorAdapter
from ctxman.adapters.generic import GenericAdapter
from ctxman.models.source import InjectionSource

_ADAPTER_MAP: dict[Platform, InjectionAdapter] = {
    Platform.CLAUDE_CODE: ClaudeCodeAdapter(),
    Platform.CURSOR: CursorAdapter(),
    Platform.GENERIC: GenericAdapter(),
}


def run_inventory(path: Path) -> tuple[list[InjectionSource], Platform]:
    """Detect platform and list all injection sources. Never raises."""
    if not path.exists():
        return [], Platform.GENERIC

    platform = detect_platform(path)
    adapter = _ADAPTER_MAP.get(platform, _ADAPTER_MAP[Platform.GENERIC])

    try:
        sources = adapter.list_sources(path)
    except Exception:
        sources = []

    return sources, platform
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_pipeline.py -v
```

Expected: 4 tests PASS

```bash
git add ctxman/pipeline/inventory.py tests/test_pipeline.py
git commit -m "feat(ctxman): inventory pipeline stage (platform detect + source listing)"
```

---

## Task 8: Pipeline — SCORER (Tier 1 + Tier 2)

**Files:**
- Create: `ctxman/pipeline/scorer.py`
- Test: `tests/test_scorer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scorer.py`:

```python
from ctxman.models.source import Chunk
from ctxman.pipeline.scorer import score_chunks_structural, score_chunks_tfidf


def test_structural_scores_header_higher():
    header_chunk = Chunk(text="## Important Rule", start_line=1, end_line=1, token_count=3)
    body_chunk = Chunk(text="Some regular text here.", start_line=3, end_line=3, token_count=5)
    score_chunks_structural([header_chunk, body_chunk])
    assert header_chunk.importance_score > body_chunk.importance_score


def test_structural_scores_trigger_marker():
    trigger_chunk = Chunk(text="Trigger: git, commit", start_line=1, end_line=1, token_count=4)
    plain_chunk = Chunk(text="Regular content.", start_line=3, end_line=3, token_count=2)
    score_chunks_structural([trigger_chunk, plain_chunk])
    assert trigger_chunk.importance_score > plain_chunk.importance_score


def test_structural_all_chunks_get_score():
    chunks = [
        Chunk(text=f"text {i}", start_line=i, end_line=i, token_count=2)
        for i in range(5)
    ]
    score_chunks_structural(chunks)
    assert all(c.importance_score >= 0 for c in chunks)


def test_tfidf_returns_scores(complex_project):
    from ctxman.pipeline.inventory import run_inventory
    sources, _ = run_inventory(complex_project)
    all_chunks = [c for s in sources for c in s.chunks]
    score_chunks_tfidf(all_chunks)
    assert any(c.importance_score > 0 for c in all_chunks)


def test_tfidf_empty_input():
    score_chunks_tfidf([])  # must not raise
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_scorer.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/pipeline/scorer.py**

```python
import re
from ctxman.models.source import Chunk

_TRIGGER_PATTERN = re.compile(r"^(trigger|트리거)\s*:", re.IGNORECASE)
_BOLD_PATTERN = re.compile(r"\*\*.+?\*\*")


def score_chunks_structural(chunks: list[Chunk]) -> None:
    """Tier 1: score in-place based on structural signals."""
    for chunk in chunks:
        score = 0.0
        text = chunk.text

        # Header level (# = 3pts, ## = 2pts, ### = 1pt)
        if text.startswith("# "):
            score += 3.0
        elif text.startswith("## "):
            score += 2.0
        elif text.startswith("### "):
            score += 1.0

        # Trigger marker
        if _TRIGGER_PATTERN.search(text):
            score += 2.0

        # Bold text presence
        score += len(_BOLD_PATTERN.findall(text)) * 0.5

        # List items (instruction density)
        list_items = sum(1 for line in text.splitlines() if line.strip().startswith(("- ", "* ", "1.")))
        score += list_items * 0.3

        chunk.importance_score = score


def score_chunks_tfidf(chunks: list[Chunk]) -> None:
    """Tier 2: score in-place using TF-IDF cross-chunk importance."""
    if not chunks:
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        texts = [c.text for c in chunks]
        vectorizer = TfidfVectorizer(max_features=500, stop_words=None)
        matrix = vectorizer.fit_transform(texts)
        # Mean TF-IDF score per chunk = proxy for information density
        scores = np.asarray(matrix.mean(axis=1)).flatten()
        for chunk, score in zip(chunks, scores):
            chunk.importance_score += float(score)
    except ImportError:
        pass  # graceful skip if scikit-learn not installed
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_scorer.py -v
```

Expected: 5 tests PASS

```bash
git add ctxman/pipeline/scorer.py tests/test_scorer.py
git commit -m "feat(ctxman): scorer pipeline (Tier1 structural + Tier2 TF-IDF)"
```

---

## Task 9: Pipeline — DEDUP

**Files:**
- Create: `ctxman/pipeline/dedup.py`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_dedup.py`:

```python
from pathlib import Path
from ctxman.models.source import Chunk, InjectionSource
from ctxman.pipeline.dedup import find_dedup_pairs
from ctxman.models.report import DedupPair


def _make_source(path: str, text: str) -> InjectionSource:
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=None,
        chunks=[Chunk(text=text, start_line=1, end_line=1, token_count=len(text.split()))],
    )


def test_identical_sources_are_high_confidence():
    text = "Never force push main. Always run tests before deploy."
    s1 = _make_source("rules/git.md", text)
    s2 = _make_source("rules/duplicate.md", text)
    pairs = find_dedup_pairs([s1, s2])
    assert len(pairs) >= 1
    assert pairs[0].confidence == "HIGH"


def test_different_sources_produce_no_high_pairs():
    s1 = _make_source("rules/git.md", "Git rules: never force push main branch.")
    s2 = _make_source("rules/python.md", "Python rules: use type hints and write tests.")
    pairs = find_dedup_pairs([s1, s2])
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]
    assert len(high_pairs) == 0


def test_single_source_returns_empty():
    s = _make_source("rules/git.md", "Some content here.")
    pairs = find_dedup_pairs([s])
    assert pairs == []


def test_empty_list_returns_empty():
    assert find_dedup_pairs([]) == []


def test_confidence_thresholds():
    from ctxman.pipeline.dedup import _confidence
    assert _confidence(0.95) == "HIGH"
    assert _confidence(0.80) == "MEDIUM"
    assert _confidence(0.50) == "LOW"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_dedup.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/pipeline/dedup.py**

```python
from ctxman.models.source import InjectionSource
from ctxman.models.report import DedupPair

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.75


def _confidence(similarity: float) -> str:
    if similarity >= _HIGH_THRESHOLD:
        return "HIGH"
    if similarity >= _MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def find_dedup_pairs(sources: list[InjectionSource]) -> list[DedupPair]:
    """Find semantically similar source pairs using cosine similarity.
    Falls back to TF-IDF if sentence-transformers not installed.
    Never raises.
    """
    if len(sources) < 2:
        return []

    texts = [" ".join(c.text for c in s.chunks) for s in sources]

    try:
        similarities = _embed_and_compare(texts)
    except Exception:
        similarities = _tfidf_compare(texts)

    pairs: list[DedupPair] = []
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            sim = similarities[i][j]
            pairs.append(
                DedupPair(
                    source_a=sources[i].path,
                    source_b=sources[j].path,
                    similarity=round(sim, 4),
                    confidence=_confidence(sim),
                )
            )

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs


def _embed_and_compare(texts: list[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, normalize_embeddings=True)
    sim_matrix = (embeddings @ embeddings.T).tolist()
    return sim_matrix


def _tfidf_compare(texts: list[str]) -> list[list[float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(matrix).tolist()
    return sim_matrix
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_dedup.py -v
```

Expected: 5 tests PASS (sentence-transformers may download model on first run)

```bash
git add ctxman/pipeline/dedup.py tests/test_dedup.py
git commit -m "feat(ctxman): dedup pipeline (cosine similarity, confidence tiers)"
```

---

## Task 10: Pipeline — TRIGGER

**Files:**
- Create: `ctxman/pipeline/trigger.py`
- Test: `tests/test_trigger.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_trigger.py`:

```python
from pathlib import Path
from ctxman.models.source import Chunk, InjectionSource
from ctxman.pipeline.trigger import extract_triggers
from ctxman.models.report import TriggerResult


def _make_source(path: str, text: str, trigger: str | None = None) -> InjectionSource:
    return InjectionSource(
        path=Path(path),
        source_type="rule",
        trigger=trigger,
        chunks=[Chunk(text=text, start_line=1, end_line=len(text.splitlines()), token_count=10)],
    )


def test_extracts_explicit_trigger():
    source = _make_source(
        "rules/git.md",
        "## Git Rules\n\nTrigger: git, commit, push\n\nNever force push.",
        trigger="git, commit, push",
    )
    results = extract_triggers([source])
    assert len(results) == 1
    assert "git" in results[0].keywords
    assert results[0].method == "parsed"


def test_falls_back_to_tfidf_when_no_trigger():
    source = _make_source(
        "rules/python.md",
        "Always use type hints. Write pytest tests. Use dataclasses over dicts.",
    )
    results = extract_triggers([source])
    assert len(results) == 1
    assert len(results[0].keywords) > 0
    assert results[0].method == "tfidf"


def test_empty_sources():
    assert extract_triggers([]) == []


def test_trigger_keywords_are_strings():
    source = _make_source(
        "rules/docs.md",
        "Trigger: readme, documentation\n\nKeep docs updated.",
        trigger="readme, documentation",
    )
    results = extract_triggers([source])
    assert all(isinstance(k, str) for k in results[0].keywords)
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_trigger.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/pipeline/trigger.py**

```python
from ctxman.models.source import InjectionSource
from ctxman.models.report import TriggerResult


def extract_triggers(sources: list[InjectionSource]) -> list[TriggerResult]:
    """Extract trigger keywords from each source. Never raises."""
    results: list[TriggerResult] = []
    for source in sources:
        if source.trigger:
            keywords = [k.strip() for k in source.trigger.split(",") if k.strip()]
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="parsed")
            )
        else:
            keywords = _tfidf_keywords(source)
            results.append(
                TriggerResult(source=source.path, keywords=keywords, method="tfidf")
            )
    return results


def _tfidf_keywords(source: InjectionSource, top_n: int = 5) -> list[str]:
    """Extract top-N TF-IDF keywords from source text."""
    text = " ".join(c.text for c in source.chunks)
    if not text.strip():
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
        matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = np.asarray(matrix.todense()).flatten()
        top_indices = scores.argsort()[::-1][:top_n]
        return [feature_names[i] for i in top_indices if scores[i] > 0]
    except Exception:
        # fallback: split and return most common words
        words = [w.lower().strip(".,!?#*") for w in text.split()]
        freq: dict[str, int] = {}
        for w in words:
            if len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:top_n]
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_trigger.py -v
```

Expected: 4 tests PASS

```bash
git add ctxman/pipeline/trigger.py tests/test_trigger.py
git commit -m "feat(ctxman): trigger extraction (regex parsed + TF-IDF fallback)"
```

---

## Task 11: ctxman analyze command

**Files:**
- Create: `ctxman/cli/main.py`
- Create: `ctxman/cli/analyze.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner
from ctxman.cli.main import app

runner = CliRunner()


def test_analyze_empty_project(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert result.exit_code == 0
    assert "설정 없음" in result.output or "No config" in result.output


def test_analyze_minimal_project(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project)])
    assert result.exit_code == 0
    assert "token" in result.output.lower() or "토큰" in result.output


def test_analyze_complex_project(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project)])
    assert result.exit_code == 0
    # Should show token count and dedup findings
    assert any(x in result.output for x in ["token", "토큰", "중복", "dedup"])


def test_analyze_current_dir_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# test")
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 0


def test_analyze_json_flag(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert "total_tokens" in data
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_cli.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create ctxman/cli/main.py**

```python
import typer
from ctxman.cli.analyze import analyze_cmd

app = typer.Typer(name="ctxman", help="Static Instruction Injection Optimizer")
app.command("analyze")(analyze_cmd)
```

- [ ] **Step 4: Create ctxman/cli/analyze.py**

```python
import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from ctxman.pipeline.inventory import run_inventory
from ctxman.pipeline.scorer import score_chunks_structural, score_chunks_tfidf
from ctxman.pipeline.dedup import find_dedup_pairs
from ctxman.pipeline.trigger import extract_triggers
from ctxman.models.report import AnalysisReport

console = Console()


def analyze_cmd(
    path: Path = typer.Argument(default=None, help="Project directory to analyze"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    no_semantic: bool = typer.Option(False, "--no-semantic", help="Skip sentence-transformers"),
):
    """Analyze static token injection in an LLM agent project."""
    target = path or Path.cwd()

    sources, platform = run_inventory(target)

    if not sources:
        if output_json:
            typer.echo(json.dumps({"total_tokens": 0, "sources": [], "level": 0}))
        else:
            console.print(f"[yellow]설정 없음[/yellow] — {target}")
            console.print("추천: [bold]ctxman init[/bold] 으로 시작하세요.")
        return

    # Score
    all_chunks = [c for s in sources for c in s.chunks]
    score_chunks_structural(all_chunks)
    score_chunks_tfidf(all_chunks)

    # Dedup
    pairs = [] if no_semantic else find_dedup_pairs(sources)
    high_pairs = [p for p in pairs if p.confidence == "HIGH"]

    # Trigger
    trigger_results = extract_triggers(sources)

    total_tokens = sum(s.token_count for s in sources)
    level = _determine_level(sources)

    report = AnalysisReport(
        total_tokens=total_tokens,
        sources=sources,
        dedup_pairs=pairs,
        trigger_results=trigger_results,
        level=level,
    )

    if output_json:
        typer.echo(json.dumps({
            "total_tokens": report.total_tokens,
            "level": report.level,
            "platform": platform.value,
            "source_count": len(sources),
            "dedup_high": len(high_pairs),
            "sources": [
                {"path": str(s.path), "type": s.source_type, "tokens": s.token_count}
                for s in sources
            ],
        }))
        return

    _render_report(report, platform.value, target)


def _determine_level(sources) -> int:
    if not sources:
        return 0
    total = sum(s.token_count for s in sources)
    if total < 500:
        return 1
    if len(sources) < 5:
        return 2
    return 3


def _render_report(report: AnalysisReport, platform: str, target: Path) -> None:
    console.print(f"\n[bold]ctxman analyze[/bold] — {target}")
    console.print(f"Platform: [cyan]{platform}[/cyan]\n")

    table = Table(title="주입 소스")
    table.add_column("파일", style="dim")
    table.add_column("타입")
    table.add_column("토큰", justify="right")

    for s in report.sources:
        table.add_row(str(s.path.name), s.source_type, str(s.token_count))

    console.print(table)
    console.print(f"\n[bold]총 토큰[/bold]: {report.total_tokens:,}")

    high_pairs = [p for p in report.dedup_pairs if p.confidence == "HIGH"]
    if high_pairs:
        console.print(f"[red]중복 탐지[/red]: {len(high_pairs)}쌍 (HIGH confidence)")
        for p in high_pairs:
            console.print(f"  - {p.source_a.name} ↔ {p.source_b.name} ({p.similarity:.2%})")

    if report.level <= 1:
        console.print("\n[green]최적화 불필요[/green] — 설정이 적정합니다.")
    else:
        console.print("\n추천: [bold]ctxman optimize --dry-run[/bold] 으로 최적화 미리보기")
```

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_cli.py -v
```

Expected: 5 tests PASS

```bash
git add ctxman/cli/ tests/test_cli.py
git commit -m "feat(ctxman): analyze command with level-aware output and JSON mode"
```

---

## Task 12: ctxman init + scaffold

**Files:**
- Create: `ctxman/cli/init_cmd.py`
- Create: `ctxman/cli/scaffold.py`
- Create: `ctxman/scaffold/generator.py`
- Create: `ctxman/scaffold/templates/claude-code-base/CLAUDE.md`
- Create: `ctxman/scaffold/templates/claude-code-base/rules/git.md`
- Create: `ctxman/scaffold/templates/python-backend/CLAUDE.md`
- Modify: `ctxman/cli/main.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_init_creates_claude_md(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()


def test_init_creates_rules_dir(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    assert (tmp_path / ".claude" / "rules").is_dir()


def test_scaffold_python_backend(tmp_path):
    result = runner.invoke(app, ["scaffold", "--type", "python-backend", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".claude" / "rules").is_dir()


def test_scaffold_unknown_type_exits_gracefully(tmp_path):
    result = runner.invoke(app, ["scaffold", "--type", "unknown-xyz", str(tmp_path)])
    assert result.exit_code == 0  # graceful, not crash
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_cli.py -k "init or scaffold" -v
```

Expected: command not found errors

- [ ] **Step 3: Create template files**

`ctxman/scaffold/templates/claude-code-base/CLAUDE.md`:
```markdown
# Project

## Core Rules

- Write tests before implementation (TDD)
- Keep functions small and focused
- Document non-obvious decisions

## Trigger Table

| Trigger | Rule File |
|---------|-----------|
| git, commit, push | rules/git.md |
```

`ctxman/scaffold/templates/claude-code-base/rules/git.md`:
```markdown
# Git Rules

Trigger: git, commit, push

## Rules

- Never force push to main or master
- Write descriptive commit messages
- One logical change per commit
```

`ctxman/scaffold/templates/python-backend/CLAUDE.md`:
```markdown
# Python Backend Project

## Core Rules

- Use type hints on all functions
- Write pytest tests for all new code
- Use dataclasses over dicts for structured data

## Trigger Table

| Trigger | Rule File |
|---------|-----------|
| python, pytest, test | rules/python.md |
| deploy, production | rules/deploy.md |
```

- [ ] **Step 4: Create ctxman/scaffold/generator.py**

```python
import shutil
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_AVAILABLE_TYPES = {"claude-code-base", "python-backend"}


def scaffold_project(project_path: Path, template_type: str) -> bool:
    """Copy template files into project_path. Returns True on success."""
    template_dir = _TEMPLATES_DIR / template_type
    if not template_dir.exists():
        return False

    project_path.mkdir(parents=True, exist_ok=True)
    for src in template_dir.rglob("*"):
        if src.is_file():
            rel = src.relative_to(template_dir)
            dst = project_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return True


def available_types() -> list[str]:
    return sorted(_AVAILABLE_TYPES)
```

- [ ] **Step 5: Create ctxman/cli/init_cmd.py and scaffold.py**

`ctxman/cli/init_cmd.py`:
```python
from pathlib import Path
import typer
from rich.console import Console
from ctxman.scaffold.generator import scaffold_project

console = Console()


def init_cmd(
    path: Path = typer.Argument(default=None, help="Project directory"),
):
    """Initialize a new ctxman-optimized project structure."""
    target = path or Path.cwd()
    success = scaffold_project(target, "claude-code-base")
    if success:
        console.print(f"[green]초기화 완료[/green] — {target}")
        console.print("다음 단계: [bold]ctxman watch[/bold] 로 세션 데이터 수집 시작")
    else:
        console.print("[red]초기화 실패[/red]")
```

`ctxman/cli/scaffold.py`:
```python
from pathlib import Path
import typer
from rich.console import Console
from ctxman.scaffold.generator import scaffold_project, available_types

console = Console()


def scaffold_cmd(
    template_type: str = typer.Option("claude-code-base", "--type", help="Template type"),
    path: Path = typer.Argument(default=None),
):
    """Generate project-type-specific rule templates."""
    target = path or Path.cwd()
    success = scaffold_project(target, template_type)
    if success:
        console.print(f"[green]스캐폴딩 완료[/green] ({template_type}) — {target}")
    else:
        console.print(f"[yellow]알 수 없는 타입:[/yellow] {template_type}")
        console.print(f"사용 가능: {', '.join(available_types())}")
```

- [ ] **Step 6: Update ctxman/cli/main.py**

```python
import typer
from ctxman.cli.analyze import analyze_cmd
from ctxman.cli.init_cmd import init_cmd
from ctxman.cli.scaffold import scaffold_cmd

app = typer.Typer(name="ctxman", help="Static Instruction Injection Optimizer")
app.command("analyze")(analyze_cmd)
app.command("init")(init_cmd)
app.command("scaffold")(scaffold_cmd)
```

- [ ] **Step 7: Run tests and commit**

```bash
pytest tests/test_cli.py -v
```

Expected: all CLI tests PASS

```bash
git add ctxman/cli/init_cmd.py ctxman/cli/scaffold.py ctxman/cli/main.py \
        ctxman/scaffold/ tests/test_cli.py
git commit -m "feat(ctxman): init and scaffold commands with templates"
```

---

## Task 13: ctxman watch (events.jsonl)

**Files:**
- Create: `ctxman/cli/watch.py`
- Modify: `ctxman/cli/main.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
import json


def test_watch_creates_events_file(tmp_path, monkeypatch):
    events_file = tmp_path / "events.jsonl"
    # Simulate one tick by patching the watch loop
    from ctxman.cli import watch as watch_module
    monkeypatch.setattr(watch_module, "_collect_event", lambda p: {
        "session_id": "test",
        "sources_loaded": [],
        "trigger_matched": None,
    })
    watch_module.append_event(events_file, {"session_id": "test"})
    assert events_file.exists()
    line = events_file.read_text().strip()
    data = json.loads(line)
    assert "session_id" in data
```

- [ ] **Step 2: Create ctxman/cli/watch.py**

```python
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import typer
from rich.console import Console

console = Console()


def append_event(events_file: Path, event: dict) -> None:
    """Append a single event to events.jsonl."""
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _collect_event(project_path: Path) -> dict:
    """Collect a single session snapshot."""
    from ctxman.pipeline.inventory import run_inventory
    sources, _ = run_inventory(project_path)
    return {
        "sources_loaded": [str(s.path) for s in sources],
        "trigger_matched": None,
        "token_total": sum(s.token_count for s in sources),
    }


def watch_cmd(
    path: Path = typer.Argument(default=None),
    interval: int = typer.Option(60, "--interval", help="Seconds between snapshots"),
    output: Path = typer.Option(None, "--output", help="Output file (default: events.jsonl)"),
):
    """Monitor session token usage and write events.jsonl."""
    target = path or Path.cwd()
    events_file = output or target / "events.jsonl"
    console.print(f"[cyan]Watching[/cyan] {target} → {events_file} (Ctrl+C to stop)")

    session_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    try:
        while True:
            event = _collect_event(target)
            event["session_id"] = session_id
            append_event(events_file, event)
            console.print(f"  [dim]{event['ts']}[/dim] tokens={event.get('token_total', 0)}")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/yellow]")
```

- [ ] **Step 3: Update ctxman/cli/main.py**

```python
import typer
from ctxman.cli.analyze import analyze_cmd
from ctxman.cli.init_cmd import init_cmd
from ctxman.cli.scaffold import scaffold_cmd
from ctxman.cli.watch import watch_cmd

app = typer.Typer(name="ctxman", help="Static Instruction Injection Optimizer")
app.command("analyze")(analyze_cmd)
app.command("init")(init_cmd)
app.command("scaffold")(scaffold_cmd)
app.command("watch")(watch_cmd)
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_cli.py -v
```

Expected: all tests PASS

```bash
git add ctxman/cli/watch.py ctxman/cli/main.py tests/test_cli.py
git commit -m "feat(ctxman): watch command for events.jsonl session logging"
```

---

## Task 14: E2E Benchmark Tests

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write E2E tests**

Create `tests/test_e2e.py`:

```python
"""
E2E benchmark tests — validate core invariants across all user levels.
"""
import json
import time
from pathlib import Path
from typer.testing import CliRunner
from ctxman.cli.main import app

runner = CliRunner()


# ─── Benchmark-0: Empty project ───────────────────────────────────────────────

def test_benchmark0_empty_no_crash(empty_project):
    """Empty project must exit 0, never crash."""
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert result.exit_code == 0, result.output


def test_benchmark0_empty_json_valid(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] == 0
    assert data["level"] == 0


def test_benchmark0_shows_guidance(empty_project):
    result = runner.invoke(app, ["analyze", str(empty_project)])
    assert "init" in result.output.lower()


# ─── Benchmark-1: Minimal project ─────────────────────────────────────────────

def test_benchmark1_minimal_reports_tokens(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] > 0
    assert data["level"] >= 1


def test_benchmark1_no_dedup_on_minimal(minimal_project):
    result = runner.invoke(app, ["analyze", str(minimal_project), "--json"])
    data = json.loads(result.output)
    assert data["dedup_high"] == 0


# ─── Benchmark-2: Complex project (pmo-vault-like) ────────────────────────────

def test_benchmark2_detects_tokens(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_tokens"] > 100


def test_benchmark2_detects_duplicate(complex_project):
    """complex_project fixture has git.md and duplicate.md with identical content."""
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    data = json.loads(result.output)
    assert data["dedup_high"] >= 1, "Should detect at least 1 HIGH-confidence duplicate"


def test_benchmark2_level_3(complex_project):
    result = runner.invoke(app, ["analyze", str(complex_project), "--json"])
    data = json.loads(result.output)
    assert data["level"] >= 2


def test_benchmark2_completes_under_30_seconds(complex_project):
    start = time.time()
    result = runner.invoke(app, ["analyze", str(complex_project)])
    elapsed = time.time() - start
    assert result.exit_code == 0
    assert elapsed < 30, f"Took {elapsed:.1f}s — too slow"


# ─── Benchmark-0 for init ─────────────────────────────────────────────────────

def test_benchmark0_init_creates_structure(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".claude" / "rules").is_dir()
    # After init, analyze should report level >= 1
    result2 = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    data = json.loads(result2.output)
    assert data["level"] >= 1
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS (sentence-transformers may be slow on first run)

- [ ] **Step 3: Run benchmark timing check separately**

```bash
pytest tests/test_e2e.py::test_benchmark2_completes_under_30_seconds -v -s
```

Expected: PASS with timing < 30s

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test(ctxman): E2E benchmarks Benchmark-0 through Benchmark-2"
```

---

## Task 15: README + PyPI Packaging

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

```markdown
# ctxman — Context Instruction Manager

Static Instruction Injection Optimizer for LLM agents (Claude Code, Cursor, Copilot).

Addresses the **SIOP (Static Instruction Injection Optimization Problem)** — 
an unaddressed layer that RTK and context-mode don't touch.

## Quick Start

\```bash
pip install ctxman

# Analyze any project (works on empty projects too)
ctxman analyze .

# Initialize a new project
ctxman init

# Generate project-type templates
ctxman scaffold --type python-backend
\```

## Example Output

\```
ctxman analyze — /Users/alice/my-project
Platform: claude_code

┌─────────────────┬──────────┬───────┐
│ 파일            │ 타입     │ 토큰  │
├─────────────────┼──────────┼───────┤
│ CLAUDE.md       │ claude_md│  342  │
│ rules/git.md    │ rule     │  180  │
│ rules/python.md │ rule     │  210  │
└─────────────────┴──────────┴───────┘

총 토큰: 732
중복 탐지: 1쌍 (HIGH confidence)
  - git.md ↔ duplicate.md (97.3%)

추천: ctxman optimize --dry-run 으로 최적화 미리보기
\```

## Supported Platforms

| Platform | Detection |
|----------|-----------|
| Claude Code | `.claude/`, `CLAUDE.md` |
| Cursor | `.cursor/`, `.cursorrules` |
| Generic | `*.md` scan |

## Commands

| Command | Description |
|---------|-------------|
| `ctxman analyze [path]` | Analyze token injection |
| `ctxman init [path]` | Initialize project structure |
| `ctxman scaffold --type <t>` | Generate rule templates |
| `ctxman watch [path]` | Monitor session token usage |

## Algorithm

5-stage pipeline: **Inventory → Tokenize → Score → Dedup → Trigger**

- **Score**: Structural signals (Tier 1) + TF-IDF (Tier 2)
- **Dedup**: Cosine similarity with confidence tiers (HIGH/MEDIUM/LOW)
- **Trigger**: Regex-parsed + TF-IDF auto-extraction

## Development

\```bash
pip install -e ".[dev]"
pytest tests/
\```
```

- [ ] **Step 2: Verify package installs cleanly**

```bash
pip install -e .
ctxman --help
```

Expected: help text showing analyze, init, scaffold, watch commands

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs(ctxman): README with quick start, commands, algorithm overview"
```

- [ ] **Step 5: Tag v0.1.0**

```bash
git tag v0.1.0
```

---

## Self-Review

**Spec coverage check:**

| 스펙 요구사항 | 커버 Task |
|---|---|
| Level 0~3 graceful degradation | Task 7 (inventory returns []), Task 11 (empty output) |
| Platform auto-detection | Task 3 |
| Claude Code adapter | Task 5 |
| Generic adapter (empty project) | Task 6 |
| 5단계 파이프라인 | Task 7~10 |
| 3-Tier Scorer (Tier 1+2) | Task 8 |
| DEDUP cosine similarity + 신뢰도 | Task 9 |
| TRIGGER extraction | Task 10 |
| ctxman analyze command | Task 11 |
| ctxman init + scaffold | Task 12 |
| ctxman watch + events.jsonl | Task 13 |
| Benchmark-0 (빈 프로젝트 no crash) | Task 14 |
| Benchmark-2 (pmo-vault 중복 탐지) | Task 14 |
| README + PyPI | Task 15 |
| Cursor adapter | Task 6 |
| tiktoken fallback (char count) | Task 4 |
| sentence-transformers fallback (TF-IDF) | Task 9 |

**Placeholder scan:** 없음. 모든 코드 블록에 실제 구현 포함.

**Type consistency:**
- `InjectionSource.chunks: list[Chunk]` — Task 2 정의, Task 5~9 일관 사용
- `AnalysisReport.sources: list[InjectionSource]` — Task 2 정의, Task 11 사용
- `DedupPair.confidence: str` — Task 2 정의, Task 9 `_confidence()` 일관 반환
- `find_dedup_pairs()` — Task 9 정의, Task 11 analyze.py에서 호출
