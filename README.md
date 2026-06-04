# rune

```
─────────────────────────────────────────────────────────
  ᚱᚢᚾᛖ  rune v0.1  ·  static instruction injection optimizer
─────────────────────────────────────────────────────────
```

Your LLM agent reads `CLAUDE.md`, `.cursorrules`, and a pile of rules files
before every single response. You never measured how much that costs.

**rune** finds the waste.

## What it does

- **analyze** — count every token injected before your agent speaks.<br>
  　<sub>tiktoken · platform auto-detection · works on empty projects</sub>
- **dedup** — find rules you wrote twice (you did).<br>
  　<sub>sentence-transformers · cosine similarity · HIGH / MEDIUM / LOW confidence</sub>
- **trigger** — discover which rules fire conditionally vs. always.<br>
  　<sub>TF-IDF keyword extraction · parsed trigger markers</sub>
- **scaffold** — bootstrap lean rule structures from templates.<br>
  　<sub>claude-code-base · python-backend · trigger-first layout</sub>
- **watch** — stream live session events to `events.jsonl` for later analysis.<br>
  　<sub>file-watch loop · JSON event log</sub>

## Quick Start

```bash
pip install rune

rune analyze .          # works on empty projects — never crashes
rune init               # bootstrap CLAUDE.md + .claude/rules/
rune scaffold --type python-backend
rune watch .            # start logging session events
```

<details>
<summary>Example output</summary>

```
rune analyze — ~/my-project
Platform: claude_code

  파일                              타입        토큰
  ──────────────────────────────────────────────────
  CLAUDE.md                         claude_md    342
  .claude/rules/git.md              rule         180
  .claude/rules/python.md           rule         210
  .claude/rules/deploy.md           rule         195
  .claude/rules/security.md         rule         220

총 토큰: 1,147
중복 탐지: 1쌍 (HIGH confidence)
  - .claude/rules/git.md ↔ .claude/rules/deploy.md (97.3%)

추천: rune optimize --dry-run 으로 최적화 미리보기
```

</details>

## Supported Platforms

| Platform | Detection | Status |
|---|---|---|
| **Claude Code** | `.claude/` directory · `CLAUDE.md` | ✅ Stable |
| **Cursor** | `.cursor/` directory · `.cursorrules` | 🔜 Planned |
| **GitHub Copilot** | `.github/copilot-instructions.md` · `.github/copilot/` | 🔜 Planned |
| **Gemini CLI** | `GEMINI.md` · `.gemini/` directory | 🔜 Planned |
| **Windsurf** | `.windsurfrules` | 🔜 Planned |
| **OpenCode** | `.opencode/` directory | 🔜 Planned |
| **Generic** | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` scan | ✅ Stable |

## Commands

| Command | Description |
|---|---|
| `rune analyze [path]` | Analyze token injection footprint |
| `rune analyze --json` | Machine-readable JSON output |
| `rune analyze --no-semantic` | Skip sentence-transformers (faster, less accurate dedup) |
| `rune init [path]` | Initialize recommended project structure |
| `rune scaffold --type <type>` | Generate project-type rule templates |
| `rune watch [path]` | Monitor session events → `events.jsonl` |

## User Levels

rune never crashes on edge cases. It adapts output to what you actually have.

| Level | What you have | rune output |
|---|---|---|
| 0 | No config at all | Guidance to run `rune init` |
| 1 | A single `CLAUDE.md` | Token count, baseline established |
| 2 | Some rules (3–4 files) | Dedup analysis + trigger suggestions |
| 3 | Heavy setup (5+ sources) | Full optimization report |

## Pipeline

```
INVENTORY → TOKENIZE → SCORE → DEDUP → TRIGGER
```

```
rune/
├── adapters/       # platform detection + source listing
│   ├── base.py     # Platform enum, detect_platform(), InjectionAdapter ABC
│   ├── claude_code.py
│   ├── cursor.py
│   └── generic.py
├── pipeline/
│   ├── inventory.py  # orchestrates adapter selection
│   ├── tokenizer.py  # tiktoken + char-count fallback, paragraph chunking
│   ├── scorer.py     # tier-1 structural + tier-2 TF-IDF importance
│   ├── dedup.py      # cosine similarity (sentence-transformers → TF-IDF)
│   └── trigger.py    # keyword extraction (parsed markers → TF-IDF)
├── models/
│   ├── source.py     # Chunk, InjectionSource
│   └── report.py     # DedupPair, TriggerResult, AnalysisReport
├── cli/
│   ├── main.py       # typer app entry point
│   ├── analyze.py    # rune analyze
│   ├── init_cmd.py   # rune init
│   ├── scaffold.py   # rune scaffold
│   └── watch.py      # rune watch
└── scaffold/
    └── templates/    # claude-code-base, python-backend
```

## Research

rune addresses the **Static Instruction Injection Optimization Problem (SIOP)** —
the static config layer (`CLAUDE.md`, `.cursorrules`, `rules/`) injected before every LLM session
has no tooling to measure or optimize its token footprint.

Existing tools (RTK, context-mode, summarization) target *tool output* and *conversation history*.
rune targets the *pre-session static layer* — a different, unaddressed problem.

The dedup and trigger results from `rune analyze` quantify what can be recovered through:
- lazy-loading (trigger-gated rules loaded on demand)
- deduplication (merge identical/near-identical rules)
- verbatim compaction (remove redundant prose within rules)

## License

MIT

```
                  ᚠ    ᚢ    ᚦ    ᚨ    ᚱ    ᚲ
                  ᚷ    ᚹ    ᚺ    ᚾ    ᛁ    ᛃ
                  ᛇ    ᛈ    ᛉ    ᛊ    ᛏ    ᛒ
                  ᛖ    ᛗ    ᛚ    ᛜ    ᛞ    ᛟ

                        ᚱᚢᚾᛖ
                  every token has a cost
```
