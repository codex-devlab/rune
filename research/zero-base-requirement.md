# 제로베이스 & 범용성 요구사항

> 작성일: 2026-06-03
> 배경: 기존 설계(improvement-plan.md)가 pmo-vault처럼 이미 비대한 프로젝트를 전제로 했음.
>       처음 설치하는 사용자, 아무 설정도 없는 사용자에게도 동작해야 한다는 제약 추가.

---

## 문제 정의

### 기존 설계의 전제 (잘못된 가정)

```
전제: 사용자가 이미 CLAUDE.md × 4, rules × 11, memory 등을 가지고 있다
전제: 최적화할 "낭비"가 이미 존재한다
전제: token_usage.jsonl에 692개 세션이 쌓여 있다
```

### 실제 사용자 스펙트럼

```
Level 0 — 완전 신규
  - Claude Code 방금 설치
  - CLAUDE.md 없음, rules/ 없음, memory 없음
  - token_usage.jsonl 없음
  - "뭘 어떻게 시작해야 하지?"

Level 1 — 초기 사용자
  - CLAUDE.md 1개 (기본 설정만)
  - rules 0-2개
  - 세션 기록 < 10개
  - 최적화할 낭비 거의 없음

Level 2 — 중간 사용자
  - CLAUDE.md 1-2개, rules 3-5개
  - 세션 기록 수십 개
  - 가끔 압축 경험

Level 3 — Heavy User (기존 설계 대상)
  - CLAUDE.md × 4+, rules × 10+, memory 대량
  - 세션 기록 수백 개, 압축 빈발
  - pmo-vault 같은 복잡 프로젝트
```

**기존 설계는 Level 3 전용이었음 → Level 0-2에서 쓸모없거나 오류 발생**

---

## 제로베이스 사용자 시나리오

### 시나리오 A: 완전 신규 (Level 0)

```bash
pip install rune
cd my-new-project
rune analyze .

# 기존 설계 출력 (문제):
❌ Error: No CLAUDE.md found
❌ Error: No rules/ directory found
❌ Error: token_usage.jsonl not found

# 개선 출력 (범용):
📊 rune analyze — /Users/alice/my-new-project

현재 상태: Claude Code 설정 없음

추천 액션:
  1. rune init          → 권장 CLAUDE.md 구조 생성
  2. rune scaffold      → 프로젝트 유형별 rules 템플릿 생성
  3. rune watch         → 세션 모니터링 시작 (데이터 수집)

현재 최적화할 내용 없음 — 설정을 먼저 구성하세요.
```

### 시나리오 B: 초기 사용자 (Level 1)

```bash
rune analyze .

# 출력:
📊 Context Analysis — my-project

주입 소스:
  CLAUDE.md (1개):   342 tokens  ✅ 적정
  rules (0개):         0 tokens
  합계:              342 tokens

상태: 최적화 불필요 (설정이 작음)

추천:
  - 프로젝트가 성장하면 rune analyze로 재확인
  - rules 추가 시 rune scaffold --rules로 트리거 구조 자동 설정
```

### 시나리오 C: 범용 (어떤 구조든)

```bash
# Cursor 프로젝트
rune analyze . --platform cursor
→ .cursorrules 파싱, cursor 설정 분석

# 일반 마크다운 기반 에이전트
rune analyze . --platform generic
→ *.md 파일 전체 스캔, 주입 패턴 추론

# 자동 감지
rune analyze .
→ 플랫폼 자동 감지 (.claude/ → claude_code, .cursor/ → cursor, 없으면 generic)
```

---

## 범용성을 위한 설계 원칙

### 원칙 1: Graceful Degradation (우아한 저하)

모든 명령이 빈 프로젝트에서도 오류 없이 동작해야 한다.

```python
# BAD: 파일 없으면 크래시
rules = parse_rules("./rules/")  # FileNotFoundError

# GOOD: 없으면 빈 결과 + 안내
rules = adapter.list_injection_sources(project)
# → [] 반환, "rules/ 없음" 메시지 출력
```

### 원칙 2: Progressive Value (점진적 가치)

설정이 적어도 가치를 제공하고, 설정이 많아질수록 더 큰 가치를 제공한다.

```
Level 0: "현재 설정 없음. rune init으로 시작하세요." (가이드 가치)
Level 1: "설정이 적정합니다. 성장 추적 중." (모니터링 가치)
Level 2: "중복 2건 발견, 트리거 최적화 가능." (분석 가치)
Level 3: "47% 낭비 감지. 최적화 시 3,211 tokens 절감." (최적화 가치)
```

### 원칙 3: Zero-Config Start (설정 없이 시작)

```bash
# 설치 후 즉시 실행 가능
pip install rune
rune analyze .   # 어떤 디렉토리에서도 동작
```

추가 설정 파일(`~/.rune/config.yaml`) 없이도 동작. 설정은 선택사항.

### 원칙 4: Platform Auto-Detection (자동 감지)

```python
def detect_platform(path: Path) -> Platform:
    if (path / ".claude").exists():       return Platform.CLAUDE_CODE
    if (path / ".cursor").exists():       return Platform.CURSOR
    if (path / ".github/copilot").exists(): return Platform.COPILOT
    if any(path.glob("CLAUDE.md")):       return Platform.CLAUDE_CODE
    if any(path.glob(".cursorrules")):    return Platform.CURSOR
    return Platform.GENERIC               # fallback: 마크다운 기반
```

### 원칙 5: Scaffold (스캐폴딩 기능)

신규 사용자가 좋은 구조로 시작할 수 있도록 템플릿 제공.

```bash
rune init
→ CLAUDE.md 기본 구조 생성 (트리거 테이블 포함)
→ .claude/rules/ 디렉토리 생성
→ "rune watch 실행해서 사용 패턴 수집 시작" 안내

rune scaffold --type python-backend
→ Python 백엔드 프로젝트 권장 rules 템플릿 생성
→ 트리거 키워드 사전 설정된 상태로 시작

rune scaffold --type pmo-vault
→ PMO vault 스타일 rules 구조 생성
```

---

## 수정된 명령어 체계

### 기존 (heavy user 전용)

```
rune analyze    ← 기존 설정 분석
rune optimize   ← 최적화 적용
rune profile    ← 프로파일 관리
rune monitor    ← 모니터링
```

### 개선 (전체 스펙트럼 커버)

```
# 신규 사용자 진입점
rune init               → 권장 구조 생성 (zero → level 1)
rune scaffold [--type]  → 프로젝트 유형별 rules 템플릿

# 모든 레벨 공통
rune analyze [path]     → 현재 상태 분석 (Level 0도 오류 없이 동작)
rune watch              → 세션 데이터 수집 시작

# Level 2+ 부터 의미있는 명령
rune report             → 수집 데이터 기반 리포트
rune optimize           → 최적화 제안 + 적용

# Level 3 특화
rune profile [create|apply|list]
rune simulate
rune verify
```

---

## 수정된 UX 흐름

```
신규 사용자 온보딩:

Step 1: rune analyze .
        → "Claude Code 설정 없음 감지. rune init 실행 추천"

Step 2: rune init
        → CLAUDE.md + rules/ 구조 생성
        → "rune watch로 사용 패턴 수집 시작 추천"

Step 3: rune watch (백그라운드 실행)
        → 세션마다 events.jsonl 수집

Step 4 (2주 후): rune analyze .
        → 실제 데이터 기반 "이 rules는 사용 안 됨, 이 부분 중복" 탐지

Step 5: rune optimize --dry-run
        → 변경 preview

Step 6: rune optimize --apply
        → 실제 적용
```

---

## 수정된 Phase 1 범위

기존 Phase 1에 **신규 사용자 경로** 추가:

```
Day 1:    Adapter 인터페이스 + 플랫폼 자동 감지
Day 2:    Graceful degradation — 빈 프로젝트 처리
Day 3:    BASELINE (token_usage.jsonl 없으면 "데이터 없음" 안내)
Day 4:    INVENTORY — 전체 소스 열거 (없으면 빈 결과)
Day 5:    rune init / scaffold — 신규 사용자 진입점
Day 6:    SCORE Tier 1+2
Day 7-8:  TRIGGER 자동 추출
Day 9:    DEDUP 신뢰도 기반
Day 10:   SIMULATE + rune verify
Day 11:   events.jsonl 로깅
Day 12:   CLI UX — Level별 다른 출력 포맷
Day 13:   E2E 검증: Level 0 (빈 프로젝트) + Level 3 (pmo-vault)
Day 14:   README (신규/기존 사용자 구분 안내) + PyPI
```

---

## 벤치마크 수정

기존 벤치마크에 Level 0 추가:

```
Benchmark-0: 완전 빈 프로젝트 — 오류 없이 종료, 적절한 안내 출력
Benchmark-1: 단순 프로젝트 (CLAUDE.md 1개) — 정상 분석, 낭비 없음 보고
Benchmark-2: pmo-vault (11 rules, 4 CLAUDE.md) — 최적화 제안
Benchmark-3: 복잡 프로젝트 (20+ rules) — 전체 파이프라인 동작
```

---

## 관련 문서

- `improvement-plan.md` — 양 팀 교차 분석 개선안 (이 문서가 추가 보완)
- `startup-team-evaluation.md` — Startup Team 평가 기록
- `expert-team-discussion.md` — Research Team 토론 기록
