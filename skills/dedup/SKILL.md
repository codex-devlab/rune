---
name: dedup
description: Find duplicate or near-duplicate rule files and offer to merge them. Reduces token footprint by eliminating redundant instructions.
---

# rune:dedup — Duplicate Rule Detection and Merging

Find rules you wrote twice (you did) and merge them.

## Step 1 — Collect candidates

Run `rune:analyze` first (or collect sources manually) to get the list of injection files.

Only check files in the same project — don't cross projects.

## Step 2 — Detect duplicates

For each pair of files, compute similarity:

**Quick method (always available):**
```python
def jaccard(a, b):
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)
```

Thresholds:
- Jaccard ≥ 0.7 → **HIGH** — almost certainly duplicate
- Jaccard ≥ 0.4 → **MEDIUM** — significant overlap, review recommended
- Jaccard < 0.4 → skip

**Semantic method (if sentence-transformers available):**
Use cosine similarity on embeddings. HIGH ≥ 0.85, MEDIUM ≥ 0.65.

## Step 3 — Report pairs

```
중복 탐지 결과

HIGH (병합 강력 권장):
  .claude/rules/git.md ↔ .claude/rules/deploy.md
  유사도: 91.3% | 중복 토큰 절감: ~160

MEDIUM (검토 권장):
  CLAUDE.md ↔ .claude/rules/general.md
  유사도: 67.2% | 중복 토큰 절감: ~80
```

## Step 4 — Interactive merge

For each HIGH pair, ask the user:

> "`a.md`와 `b.md`를 합칠까요? (합치기 / 건너뜀 / 내용 보기)"

If **합치기**:
1. Read both files
2. Write merged content: deduplicated union of unique rules, with a comment indicating merged sources
3. Keep the file with more content as the primary, delete or empty the other
4. Show diff before applying

If **내용 보기**: Show both files side by side, then ask again.

## Step 5 — Summary

```
완료:
  병합: 2쌍
  절감 토큰: ~320 (전체의 18%)
  삭제 파일: 1개
  
다음 단계: rune:analyze 로 결과 확인
```

## Try the CLI first

```bash
rune analyze . --json
```

Parse the `dedup_pairs` field from JSON output for pair detection.
