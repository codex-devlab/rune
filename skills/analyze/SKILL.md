---
name: analyze
description: Analyze the static token injection footprint of the current LLM agent project. Use this to measure how many tokens are loaded before every agent response.
---

# rune:analyze — Static Injection Footprint Analysis

Measure every token injected into the agent context before each response.

## Step 1 — Detect platform

Check which AI agent platform this project uses:

| Signal | Platform |
|---|---|
| `.claude/` or `CLAUDE.md` | Claude Code |
| `.cursorrules` or `.cursor/` | Cursor |
| `.github/copilot-instructions.md` | GitHub Copilot |
| `GEMINI.md` or `.gemini/` | Gemini CLI |
| `.windsurfrules` | Windsurf |
| `.opencode/` | OpenCode |
| `AGENTS.md` | Generic |

## Step 2 — Collect injection sources

Collect all files that are injected before the agent responds:

**Claude Code:**
- `CLAUDE.md` (root and all parent directories up to home)
- `.claude/rules/**/*.md`
- `.claude/skills/**/SKILL.md`
- `CLAUDE.md` in subdirectories (if nested project)

**Cursor:** `.cursorrules`, `.cursor/rules/**/*.md`

**Copilot:** `.github/copilot-instructions.md`, `.github/copilot/**/*.md`

**Gemini:** `GEMINI.md`, `.gemini/**/*.md`

**Windsurf:** `.windsurfrules`

**OpenCode:** `.opencode/agents/**/*.md`

**Generic:** `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (root only)

## Step 3 — Count tokens

For each file:
1. Read the file content
2. Count tokens using this approximation: `token_count ≈ len(content) / 4` (characters ÷ 4)
3. If tiktoken is available: `import tiktoken; enc = tiktoken.get_encoding("cl100k_base"); len(enc.encode(text))`

## Step 4 — Report

Present a table sorted by token count descending:

```
rune analyze — <project path>
Platform: <detected platform>

파일                          타입        토큰
────────────────────────────────────────────
CLAUDE.md                     claude_md    342
.claude/rules/git.md          rule         180
.claude/rules/python.md       rule         210
...

총 토큰: X,XXX
```

## Step 5 — Flag issues

After the table, report:

- **중복 의심**: Any two files with >50% content overlap (quick check: shared unique words / total unique words)
- **대형 파일**: Any single file over 500 tokens
- **총계 경고**: If total > 2,000 tokens → "최적화 권장 — `rune:dedup` 실행을 고려하세요"

## Try the CLI first

If rune CLI is installed at a known path, run it directly:

```bash
# Check common locations
~/.local/bin/rune analyze . --json
# or
rune analyze . --json
```

Parse JSON output and present it. If CLI not found, proceed with manual steps above.
