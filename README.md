# rune

Static Instruction Injection Optimizer for LLM agents (Claude Code, Cursor, Copilot).

Addresses the **SIOP (Static Instruction Injection Optimization Problem)** —
an unaddressed layer that RTK and context-mode don't touch.

## Quick Start

```bash
pip install rune

# Analyze any project (works on empty projects too)
rune analyze .

# Initialize a new project
rune init

# Generate project-type templates
rune scaffold --type python-backend
```

## Example Output

```
rune analyze — /Users/alice/my-project
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

추천: rune optimize --dry-run 으로 최적화 미리보기
```

## Supported Platforms

| Platform | Detection |
|----------|-----------|
| Claude Code | `.claude/`, `CLAUDE.md` |
| Cursor | `.cursor/`, `.cursorrules` |
| Generic | `*.md` scan |

## Commands

| Command | Description |
|---------|-------------|
| `rune analyze [path]` | Analyze token injection (works on empty projects) |
| `rune analyze --json` | Output as JSON |
| `rune analyze --no-semantic` | Skip sentence-transformers (faster) |
| `rune init [path]` | Initialize recommended project structure |
| `rune scaffold --type <type>` | Generate project-type rule templates |
| `rune watch [path]` | Monitor session usage → `events.jsonl` |

## User Levels

| Level | Description | rune output |
|-------|-------------|-------------|
| 0 | No config | Guidance to run `rune init` |
| 1 | Single CLAUDE.md | Token count, no optimization needed |
| 2 | Some rules | Dedup analysis, trigger suggestions |
| 3 | Heavy user (10+ rules) | Full optimization report |

## Pipeline

```
INVENTORY → TOKENIZE → SCORE → DEDUP → TRIGGER
```

1. **INVENTORY**: Detect platform, list all injection sources
2. **TOKENIZE**: Count tokens per source (tiktoken + fallback)
3. **SCORE**: Tier 1 structural + Tier 2 TF-IDF importance scoring
4. **DEDUP**: Cosine similarity deduplication (HIGH/MEDIUM/LOW confidence)
5. **TRIGGER**: Extract keywords for lazy-loading optimization

## Research

rune addresses the **Static Instruction Injection Optimization Problem (SIOP)**:
the static config layer (CLAUDE.md, .cursorrules, rules/) injected before every LLM session
has no tooling to measure or optimize its token footprint.

- RTK/context-mode tools address *tool output* and *history* compression
- rune addresses the *static config* layer — a different, unaddressed problem

## License

MIT
