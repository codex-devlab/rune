---
name: scaffold
description: Bootstrap a lean, trigger-first rule structure for a new or existing project. Avoids the token bloat that comes from flat, always-loaded rule files.
---

# rune:scaffold — Lean Rule Structure Generator

Bootstrap a project's rule structure following the trigger-first pattern.

## Core principle

**Bad:** One giant CLAUDE.md that's always loaded (high token cost every response)  
**Good:** Small CLAUDE.md + trigger-gated rules in `.claude/rules/` (rules loaded only when relevant)

## Step 1 — Understand the project

Ask the user (or infer from existing files):

1. **프로젝트 유형**: Python backend / TypeScript frontend / fullstack / infra / general
2. **기존 규칙 유무**: 기존 CLAUDE.md나 rules 파일이 있나요?
3. **팀 규모**: 혼자 / 소규모팀 / 팀

If existing files exist, read them first — scaffold should complement, not replace.

## Step 2 — Choose template

| 유형 | 템플릿 | 생성 파일 |
|---|---|---|
| `claude-code-base` | 범용 Claude Code | CLAUDE.md + 3 rules |
| `python-backend` | Python 백엔드 | CLAUDE.md + 4 rules (python, testing, git, api) |
| `trigger-first` | 최소 베이스라인 | CLAUDE.md(최소) + 트리거 예시 1개 |

## Step 3 — Generate structure

### `claude-code-base` template

**`CLAUDE.md`** (always loaded — keep under 200 tokens):
```markdown
# Project Rules

## Core Principles
- [핵심 원칙 1-3개만]

## Rules
See `.claude/rules/` for topic-specific rules.
Trigger keywords load rules automatically.
```

**`.claude/rules/git.md`**:
```markdown
---
trigger: commit, push, branch, merge, PR, pull request
---
# Git Rules
- [git 관련 규칙]
```

**`.claude/rules/testing.md`**:
```markdown
---
trigger: test, spec, pytest, jest, coverage
---
# Testing Rules
- [테스트 관련 규칙]
```

**`.claude/rules/style.md`**:
```markdown
---
trigger: format, lint, style, type, annotation
---
# Style Rules
- [코딩 스타일 규칙]
```

### `trigger-first` template (minimal)

Just show the pattern with one example rule. User fills in content.

## Step 4 — Apply

Before writing any file:
1. Show the complete file list that will be created/modified
2. Ask: "이 구조로 생성할까요?"
3. On confirmation, write files

For existing projects with a large CLAUDE.md:
- Offer to split it: "CLAUDE.md를 분석해서 트리거 기반 rules로 분리할까요?"
- If yes, read CLAUDE.md, group sections by topic, write each as a triggered rule file

## Step 5 — Report

```
스캐폴딩 완료

생성된 파일:
  CLAUDE.md           (87 토큰)
  .claude/rules/git.md        (45 토큰, 트리거: commit/push/branch)
  .claude/rules/testing.md    (52 토큰, 트리거: test/pytest)
  .claude/rules/style.md      (38 토큰, 트리거: format/lint)

예상 절감: 항상 로딩 → 평균 ~30% (트리거 미발동 시)
다음 단계: rune:analyze 로 토큰 풋프린트 확인
```
