# 양 팀 결론 교차 분석 — 통합 개선안

> 작성일: 2026-06-03
> 분석 대상: expert-team-discussion.md (Research Team) × startup-team-evaluation.md (Startup Team)
> 목적: 두 팀의 결론 간 긴장·공백·충돌을 해소하고 최적 방향 도출

---

## 1. 교차 분석: 팀 간 긴장 지점 6개

### 긴장 1 — 스코어링: 정확도 vs 속도

| | Research Team | Startup Team |
|---|---|---|
| 방향 | perplexity 기반 self-information (정확) | Phase 1에서 제외, 구조적 신호만 사용 |
| 근거 | Selective Context 논문 검증됨 | API 비용·지연 발생, MVP 범위 초과 |
| 충돌 | 알고리즘 정확도 vs 출시 속도 | — |

**개선안:** 3단계 스코어링 티어 — 사용자가 선택

```
Tier 1 (기본, 즉시): 구조적 신호만
  - 헤더 레벨(#, ##), 볼드(**), 트리거 마커, 섹션 길이
  - 추가 의존성 없음, <100ms

Tier 2 (표준, 로컬): 구조적 + TF-IDF
  - scikit-learn TF-IDF로 cross-file 중요도 계산
  - 추가 설치 없음(requirements에 포함), <1초

Tier 3 (정밀, API): 구조적 + TF-IDF + perplexity
  - claude-haiku 또는 GPT2-small로 perplexity 계산
  - --deep-score 플래그로 명시적 opt-in
  - 비용 ~$0.001/분석 (haiku 기준)
```

→ **Phase 1 기본은 Tier 2**, `--deep-score`로 Tier 3 접근 가능하게 문을 열어둠

---

### 긴장 2 — Dedup 안전성

| | Research Team | Startup Team |
|---|---|---|
| 방향 | 쌍별 비교 후 병합 제안 (수동) | 상세 미정의 |
| 문제 | 의미론적 같아도 문맥이 달라야 하는 경우 존재 | 자동화 범위 불명확 |

**개선안:** 신뢰도 기반 3단계 Dedup

```python
# 중복 판정 임계값
DEDUP_TIERS = {
    "auto_merge":  0.95,  # 확실한 중복 → 자동 통합 제안
    "suggest":     0.80,  # 유사 → 사람 검토 제안
    "ignore":      0.70,  # 낮은 유사도 → 무시
}

# 출력 예시
⚠️  중복 탐지 (신뢰도 0.91):
    secrets-query.md:L45-52 ↔ infrastructure-update.md:L78-85
    [배타 키워드 표]
    → 제안: 공통 섹션으로 추출 후 양쪽에서 참조
    → 실행: ctxman dedup --apply [--merge | --reference | --skip]
```

추가: **"문맥 보존 플래그"** — 같은 내용이라도 양쪽 파일이 서로 다른 목적으로 명시적 중복을 허용한 경우 `# ctxman:keep-duplicate` 주석으로 예외 처리

---

### 긴장 3 — 플랫폼 범위

| | Research Team | Startup Team |
|---|---|---|
| 방향 | Adapter 패턴으로 분리 | Phase 1에 Claude Code + Cursor 포함 |
| 문제 | Adapter 설계 상세 없음 | Cursor hook 구조 차이 미분석 |

**개선안:** Adapter 인터페이스 Day 1 정의, 구현은 단계적

```python
# Day 1 정의 (인터페이스만)
class ContextAdapter(Protocol):
    def detect_project(self, path: Path) -> ProjectInfo
    def list_injection_sources(self, project: ProjectInfo) -> list[InjectionSource]
    def get_trigger_hook_path(self, project: ProjectInfo) -> Path | None
    def write_optimized_config(self, project: ProjectInfo, plan: OptimizationPlan) -> None

# Phase 1: ClaudeCodeAdapter (구현)
# Phase 1: GenericMarkdownAdapter (fallback, .md 파일 기반 모든 프로젝트)
# Phase 2: CursorAdapter
# Phase 2: CopilotAdapter
```

→ **Phase 1에 Cursor 어댑터 무리하게 포함하지 않음** — Generic adapter로 커버 가능

---

### 긴장 4 — 실측 베이스라인 부재

| | Research Team | Startup Team |
|---|---|---|
| 방향 | "pmo-vault 실제 세션 로그로 낭비 정량화" 언급 | "50%+ 절감" johnlindquist 사례 기반 가정 |
| 문제 | 실측 안 함 | 타 프로젝트 데이터로 자기 환경 가정 |

**개선안:** Phase 1 Day 1에 "베이스라인 측정 먼저"

```bash
# token_usage.jsonl 분석으로 실제 세션 토큰 구조 파악
ctxman baseline --from ~/.claude/token_usage.jsonl --last 30d

# 출력:
📈 Baseline Analysis (최근 30일, 692 세션)
─────────────────────────────────────────
평균 세션 시작 토큰: 8,432
최대:               24,891  ← 압축 트리거 빈발
중앙값:              7,103
압축 트리거 횟수:     47회 (6.8%)

시작 토큰 분포:
  < 5k:   31%
  5-10k:  44%  ← 주 구간
  10-20k: 21%
  > 20k:  4%
```

→ 이 숫자가 "시장 검증 데이터"이자 README의 핵심 hook

---

### 긴장 5 — Lazy Loading 안전성

| | Research Team | Startup Team |
|---|---|---|
| 방향 | 트리거 테이블 주입 후 on-demand 로드 | 플랫폼 협력 의존성 리스크 명시 |
| 문제 | LLM이 트리거를 놓칠 경우 rule 미로드 → 기능 누락 가능 | 해결책 없음 |

**개선안:** Simulation Mode + Safety Net

```bash
# 실제 적용 전 시뮬레이션
ctxman optimize --simulate

# 출력:
🔍 Optimization Simulation
─────────────────────────────────────────
현재 전체 주입 → 최적화 후 트리거 테이블 주입

Rule 로드 시나리오:
  "포인트 정산" 발화 → points-management.md 로드 (94% 신뢰도)
  "GitLab 버전"  발화 → infrastructure-update.md 로드 (98% 신뢰도)
  "비밀번호"     발화 → secrets-query.md 로드 (99% 신뢰도)
  ⚠️  "서버 정보"   발화 → 모호 (secrets OR infra) → 둘 다 로드 (안전 fallback)

예상 절감: 3,211 tokens (-38.1%)
안전 fallback 케이스: 2개 (로드 누락 위험 0)
```

추가: **`ctxman verify`** — 트리거 인덱스 완성 후 테스트 발화 셋으로 로드 정확도 검증

---

### 긴장 6 — 피드백 루프 단절

| | Research Team | Startup Team |
|---|---|---|
| 방향 | ACON 방식 gradient-free 반복 개선 (Phase 2) | 로드맵에 미포함 |
| 문제 | Phase 2 언제 시작할지, 어떤 데이터 필요한지 미정 | 단기 로드맵만 있음 |

**개선안:** Phase 1부터 데이터 수집 구조 삽입 (분석만, 학습 미적용)

```python
# Phase 1: 이벤트 로깅만 (로컬 저장)
~/.ctxman/events.jsonl
{
  "ts": 1748959200,
  "project": "pmo-vault",
  "session_start_tokens": 8432,
  "rules_loaded": ["points-management", "secrets-query"],
  "compression_triggered": false,
  "task_type": "inferred:weekly-report"  # 향후 분류기 입력
}

# Phase 2: 이 데이터로 ACON 방식 프로파일 자동 개선
```

---

## 2. 추가 발견: 두 팀 모두 놓친 것

### 누락 A — 토큰 측정 범위 불완전

두 팀 모두 `.claude/rules/*.md` 중심으로 분석했지만, 실제 주입 소스는 더 많습니다:

```
미분석 소스:
├── .claude/commands/*.md       ← slash 명령 정의
├── .claude/settings.json       ← 도구 허용 목록 (토큰 무시 불가)
├── ~/.claude/CLAUDE.md         ← 글로벌 설정
└── claude-mem recent context   ← 동적이지만 세션 시작 시 고정 주입
```

→ **완전한 주입 소스 인벤토리** 작성 필요 (Claude Code 내부 구조 분석 기반)

### 누락 B — Memory/recent context 최적화 미포함

Research Team 알고리즘 5단계는 모두 `rules/*.md` 대상. Startup Team 분석에서도 Memory 참조(14.6%)가 측정됐지만 최적화 방안 없음.

→ **Memory 컨텍스트 최적화** 별도 모듈로 Phase 2 포함:
- claude-mem observation TTL 기반 자동 정리
- recent context 요약 압축 (ACON 방식)

### 누락 C — 벤치마크 정의 부재

"50% 절감"이라는 목표가 있지만 어떤 조건에서 측정하는지 미정의.

→ **표준 벤치마크 셋** 정의:
```
Benchmark-1: pmo-vault (11 rules, 4 CLAUDE.md) — 실제 사례
Benchmark-2: 단순 프로젝트 (1 CLAUDE.md, rules 없음) — 하한선
Benchmark-3: 복잡 프로젝트 (20+ rules, multi-CLAUDE.md) — 상한선
측정 지표: (a) 토큰 절감율, (b) 작업 성공율, (c) 분석 소요 시간
```

---

## 3. 통합 개선 아키텍처

### 기존 (Research Team 제안)

```
Offline: Tokenize → Score → Dedup → Trigger → Index
Runtime: Trigger Table 주입 → On-demand Load
```

### 개선안 (통합)

```
                    ┌─────────────────────────────────────┐
                    │           ctxman pipeline            │
                    └─────────────────────────────────────┘

Phase 0: BASELINE     token_usage.jsonl 분석 → 실측 낭비 정량화
    │
Phase 1: INVENTORY    주입 소스 전체 열거 (rules + commands + settings + memory)
    │
Phase 2: SCORE        Tier 1/2/3 하이브리드 스코어링 (구조 + TF-IDF + perplexity opt-in)
    │
Phase 3: DEDUP        신뢰도 기반 3단계 (auto / suggest / ignore) + keep-duplicate 예외
    │
Phase 4: TRIGGER      자동 추출 + Simulation Mode + ctxman verify 검증
    │
Phase 5: OPTIMIZE     dry-run → 사람 검토 → apply
    │
Phase 6: MONITOR      events.jsonl 수집 → 압축 트리거 추적
    │
Phase 7: LEARN        ACON 방식 프로파일 자동 개선 (Phase 2 제품)
```

---

## 4. 개선된 Phase 1 범위 (2주)

### 기존 (Startup Team)

```
Day 1-2:  스캐폴딩
Day 3-4:  Token Accounting
Day 5-6:  Trigger Extraction
Day 7-8:  Cross-File Dedup
Day 9-10: Importance Scoring (구조적만)
Day 11-12: CLI UX
Day 13-14: 테스트 + 릴리즈
```

### 개선안

```
Day 1:    Adapter 인터페이스 정의 + ClaudeCodeAdapter 골격
Day 2:    BASELINE 명령 — token_usage.jsonl 파싱, 실측 숫자 확보
Day 3-4:  INVENTORY — 전체 주입 소스 열거 (rules/commands/settings/memory 포함)
Day 5:    SCORE Tier 1 (구조적 신호)
Day 6:    SCORE Tier 2 (+ TF-IDF) + --deep-score 플래그 stub
Day 7-8:  TRIGGER 자동 추출 + trigger_index.json
Day 9:    DEDUP 신뢰도 계산 + 3단계 출력
Day 10:   SIMULATE 명령 — lazy loading 시뮬레이션 + 안전 검증
Day 11:   events.jsonl 로깅 stub (분석만)
Day 12:   CLI UX + 컬러 출력 + --json 파이프라인 모드
Day 13:   pmo-vault E2E 검증 + 벤치마크 수치 확보
Day 14:   README + 데모 GIF + PyPI 배포
```

**변경 이유:**
- Day 2에 BASELINE 먼저 → "실측 X% 낭비" 숫자가 README Hook 됨
- Day 1에 Adapter 인터페이스 → Generic adapter 자동 포함
- Day 10 SIMULATE → 안전성 검증 포함
- Day 11 events 로깅 → Phase 2 피드백 루프 데이터 준비

---

## 5. 최종 개선 요약

| 항목 | 기존 | 개선 | 근거 |
|---|---|---|---|
| 스코어링 | 구조적 신호만 (Phase 1) | 3-Tier 하이브리드 (Tier 2 기본) | 정확도·속도 균형 |
| Dedup 안전성 | 병합 제안 | 신뢰도 3단계 + keep-duplicate 예외 | 문맥 보존 케이스 처리 |
| 플랫폼 | Claude Code + Cursor | Claude Code + Generic adapter | Cursor는 Phase 2 |
| 베이스라인 | johnlindquist 가정 | token_usage.jsonl 실측 (Day 2) | 자체 데이터 기반 |
| Lazy Loading | 개념만 | Simulation Mode + ctxman verify | 안전성 확보 |
| 피드백 루프 | Phase 2 (미정) | Phase 1부터 events.jsonl 수집 | 데이터 준비 |
| 주입 소스 | rules/*.md 중심 | commands/settings/memory 포함 | 완전한 인벤토리 |
| 벤치마크 | "50% 절감" (미정의) | 3종 표준 벤치마크 + 3개 지표 | 재현 가능 측정 |

---

## 6. 미해결 → 해결된 질문

| 질문 | 팀 | 개선안 결론 |
|---|---|---|
| perplexity 스코어링 언제? | 긴장 1 | Phase 1 Tier 3 opt-in으로 즉시 문 열어둠 |
| Dedup 안전 케이스 처리? | 긴장 2 | 신뢰도 임계값 + keep-duplicate 예외 |
| Cursor Phase 1 포함? | 긴장 3 | Generic adapter로 대체, Cursor Phase 2 |
| 50% 주장 근거? | 긴장 4 | Day 2 실측으로 교체 |
| Lazy loading 누락 위험? | 긴장 5 | Simulation Mode + verify 명령 |
| 피드백 루프 데이터? | 긴장 6 | Phase 1 events.jsonl 수집 stub |

---

## 관련 문서

- `context-optimization-research.md` — 논문·기법 카탈로그
- `expert-team-discussion.md` — Research Team 토론 기록
- `startup-team-evaluation.md` — Startup Team 평가 기록
- `teams.md` — 팀 구성 레지스트리
