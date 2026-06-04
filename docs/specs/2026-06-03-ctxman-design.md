# ctxman — 설계 스펙

> 작성일: 2026-06-03
> 상태: 사용자 승인 완료
> 근거 자료: research/ 디렉토리 6개 문서 (expert-team-discussion, startup-team-evaluation, improvement-plan, zero-base-requirement, teams, context-optimization-research)

---

## 1. 제품 개요

### 제품명

`ctxman` (Context Instruction Manager)

### 문제 정의 — SIOP

**Static Instruction Injection Optimization Problem (SIOP)**:

> M개의 작업 유형이 있을 때, N개 rule/config 파일 집합에서
> 작업 성능 δ를 유지하면서 주입 토큰을 최소화하는
> per-task 최적 subset을 자동으로 발견하는 문제.

기존 도구(RTK, context-mode)는 모두 동적 콘텐츠(tool output, 대화 히스토리)를 대상으로 한다. **정적 config 레이어(CLAUDE.md, rules/, .cursorrules 등)를 최적화하는 도구는 존재하지 않는다.**

### 포지셔닝

```
RTK:           tool output 압축    (39k stars) ← 다른 레이어
context-mode:  tool output 샌드박스 (16k stars) ← 다른 레이어
ctxman:        static config 최적화             ← 공백 레이어 (SIOP)
```

---

## 2. 사용자 스펙트럼 (Level 0~3)

모든 Level에서 오류 없이 동작하는 것이 핵심 불변 조건.

| Level | 설명 | 보유 자산 | ctxman 가치 |
|---|---|---|---|
| 0 | 완전 신규 | 아무것도 없음 | 구조 생성 가이드 |
| 1 | 초기 사용자 | CLAUDE.md 1개, rules 0~2개 | 현황 모니터링 |
| 2 | 중간 사용자 | rules 3~5개, 세션 수십 개 | 중복 탐지, 최적화 제안 |
| 3 | Heavy User | rules 10+, 세션 수백 개 | 전체 파이프라인, 47%+ 절감 |

---

## 3. 아키텍처

### 3-레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│  CLI Layer (typer)                                       │
│  init · scaffold · analyze · watch · report · optimize  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Core Engine (Platform-agnostic)                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Adapter  │  │ Pipeline │  │ Scorer   │  │ Report │  │
│  │ (탐지/   │  │ (5단계   │  │ (3-Tier  │  │ (Level │  │
│  │  파싱)   │  │  분석)   │  │  점수)   │  │  별출력)│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Platform Adapters                                      │
│  claude_code · cursor · copilot · generic               │
└─────────────────────────────────────────────────────────┘
```

### 플랫폼 자동 감지

```python
def detect_platform(path: Path) -> Platform:
    if (path / ".claude").exists():             return Platform.CLAUDE_CODE
    if (path / ".cursor").exists():             return Platform.CURSOR
    if (path / ".github/copilot").exists():     return Platform.COPILOT
    if any(path.glob("CLAUDE.md")):             return Platform.CLAUDE_CODE
    if any(path.glob(".cursorrules")):          return Platform.CURSOR
    return Platform.GENERIC
```

---

## 4. 컴포넌트 구조

```
ctxman/
├── cli/
│   ├── main.py          ← typer 진입점
│   ├── init.py          ← ctxman init (Level 0 진입점)
│   ├── scaffold.py      ← ctxman scaffold [--type]
│   ├── analyze.py       ← ctxman analyze [path]
│   ├── watch.py         ← ctxman watch
│   ├── report.py        ← ctxman report
│   └── optimize.py      ← ctxman optimize [--dry-run|--apply]
│
├── adapters/
│   ├── base.py          ← InjectionAdapter 추상 인터페이스
│   ├── claude_code.py   ← CLAUDE.md, .claude/rules/, skills/
│   ├── cursor.py        ← .cursorrules, .cursor/
│   ├── copilot.py       ← .github/copilot/
│   └── generic.py       ← *.md 전체 스캔
│
├── pipeline/
│   ├── inventory.py     ← Stage 1: 소스 열거
│   ├── tokenizer.py     ← Stage 2: 토큰 집계
│   ├── scorer.py        ← Stage 3: 3-Tier 점수
│   ├── dedup.py         ← Stage 4: 의미 중복 탐지
│   └── trigger.py       ← Stage 5: 트리거 추출
│
├── models/
│   ├── injection_source.py
│   ├── chunk.py
│   └── report.py
│
└── scaffold/
    ├── templates/
    │   ├── claude-code-base/
    │   ├── python-backend/
    │   └── pmo-vault/
    └── generator.py
```

### 핵심 인터페이스

```python
class InjectionAdapter(ABC):
    def detect(self, path: Path) -> bool: ...
    def list_sources(self, path: Path) -> list[InjectionSource]: ...
    # 파일 없으면 [] 반환 — 절대 예외 발생 안 함

@dataclass
class InjectionSource:
    path: Path
    type: str          # "claude_md" | "rule" | "memory" | "skill"
    trigger: str | None
    token_count: int
    chunks: list[Chunk]
```

---

## 5. 5단계 파이프라인

```
[INPUT] 프로젝트 디렉토리
    │
    ▼
Stage 1: INVENTORY
  - Adapter 플랫폼 자동 감지
  - 주입 소스 전체 열거
  - 없으면 [] 반환 (크래시 없음)
    │
    ▼
Stage 2: TOKENIZE
  - tiktoken (claude-3 tokenizer)
  - 파일 → 문단(chunk) 단위 분할
  - 소스별 토큰 수 집계
    │
    ▼
Stage 3: SCORE (3-Tier Hybrid)
  Tier 1: 구조적 신호 (항상 실행)
    → 헤더 레벨, 볼드, 트리거 마커, 목록 깊이
  Tier 2: TF-IDF (기본)
    → cross-document 상대적 중요도
  Tier 3: Perplexity (opt-in, Phase 2)
    → self-information 기반 밀도 측정
    │
    ▼
Stage 4: DEDUP
  - sentence-transformers (all-MiniLM-L6-v2)
  - pairwise cosine similarity
  - 신뢰도 3단계:
    ≥ 0.92 → HIGH   (병합 강력 권고)
    0.75~0.91 → MEDIUM (검토 권고)
    < 0.75 → LOW    (보고만)
  - 자동 제거 아닌 제안만 (의미가 같아도 문맥이 다를 수 있음)
    │
    ▼
Stage 5: TRIGGER
  - 기존 트리거 섹션 regex 파싱
  - fallback: TF-IDF 상위 5개 자동 추출
  - trigger_index.json 생성
  - Lazy Loading 시뮬레이션 (예상 절감 토큰 계산)
    │
    ▼
[OUTPUT] Level별 리포트 + 최적화 제안
```

### Level별 파이프라인 실행 범위

| Level | 실행 단계 | 출력 |
|---|---|---|
| 0 (빈 프로젝트) | 감지만 | "설정 없음. ctxman init 추천" |
| 1 (최소 설정) | 1~2단계 | 현황 표시, "최적화 불필요" |
| 2 (중간) | 1~4단계 | 중복 발견, 개선 기회 |
| 3 (Heavy) | 전체 5단계 | 절감 예측, 트리거 인덱스 생성 |

---

## 6. 명령어 체계

### 신규 사용자 진입점

```bash
ctxman init               # 권장 구조 생성 (Level 0 → 1)
ctxman scaffold [--type]  # 프로젝트 유형별 rules 템플릿
  --type python-backend
  --type pmo-vault
  --type generic
```

### 공통 (모든 Level)

```bash
ctxman analyze [path]     # 현재 상태 분석 (Level 0도 오류 없음)
ctxman watch              # 세션 데이터 수집 시작 → events.jsonl
```

### Level 2+ 부터 의미있는 명령

```bash
ctxman report             # 수집 데이터 기반 리포트
ctxman optimize --dry-run # 변경 preview
ctxman optimize --apply   # 실제 적용
```

### Level 3 특화

```bash
ctxman profile [create|apply|list]   # per-task 프로파일 관리
ctxman simulate                      # Lazy Loading 시뮬레이션
ctxman verify                        # 최적화 전후 성능 검증
```

### 신규 사용자 UX 흐름

```
Step 1: ctxman analyze .
        → "Claude Code 설정 없음 감지. ctxman init 실행 추천"

Step 2: ctxman init
        → CLAUDE.md + rules/ 구조 생성
        → "ctxman watch로 사용 패턴 수집 시작 추천"

Step 3: ctxman watch (백그라운드 실행)
        → 세션마다 events.jsonl 수집

Step 4 (2주 후): ctxman analyze .
        → 실제 데이터 기반 "이 rules는 사용 안 됨" 탐지

Step 5: ctxman optimize --dry-run
        → 변경 preview

Step 6: ctxman optimize --apply
        → 실제 적용
```

---

## 7. 데이터 흐름

```
ctxman analyze .
        │
        ▼
detect_platform()         → Platform.CLAUDE_CODE
        │
        ▼
adapter.list_sources()    → [InjectionSource × N]  (N=0 허용)
        │
        ▼
pipeline.run(sources)
  ├── tokenizer.count()   → {source: token_count}
  ├── scorer.score()      → {chunk: importance_score}
  ├── dedup.find_pairs()  → [DedupPair(confidence)]
  └── trigger.extract()   → {rule: [trigger_keywords]}
        │
        ▼
Reporter.render(level)    → Level에 맞는 출력 포맷
```

### events.jsonl 스키마 (watch 모드)

```jsonl
{"ts": "2026-06-03T10:00:00Z", "session_id": "abc", "sources_loaded": ["rules/git.md"], "trigger_matched": "git"}
{"ts": "2026-06-03T10:05:00Z", "session_id": "abc", "sources_loaded": [], "trigger_matched": null}
```

---

## 8. 에러 처리

### 핵심 원칙: Graceful Degradation

```python
# BAD
rules = parse_rules("./rules/")  # FileNotFoundError → 크래시

# GOOD
sources = adapter.list_sources(path)  # → [] + "rules/ 없음" 메시지
```

### 실패 시나리오별 처리

| 상황 | 처리 |
|---|---|
| 설정 파일 전혀 없음 | `[]` 반환, `ctxman init` 안내 |
| `sentence-transformers` 미설치 | `--no-semantic` 자동 활성, TF-IDF fallback |
| `tiktoken` 없음 | 문자 수 기반 추정 (±10% 오차 안내) |
| 플랫폼 감지 실패 | `Platform.GENERIC` fallback |
| 파일 읽기 권한 없음 | 해당 파일 skip + 경고 출력 |
| Perplexity API (비용) | opt-in 플래그 없으면 실행 안 함 |

### 의존성 리스크 + 대안

| 의존성 | 리스크 | 대안 |
|---|---|---|
| `sentence-transformers` | 첫 실행 모델 다운로드 느림 | `--no-semantic` → TF-IDF만 |
| `tiktoken` | OpenAI 라이선스 | anthropic tokenizer 또는 char 추정 |
| Perplexity API | 비용 발생 | Phase 2로 연기, 기본 비활성 |

---

## 9. 테스트 전략

### 4개 벤치마크

```
Benchmark-0: 완전 빈 디렉토리
  → 오류 없이 종료, exit code 0
  → "설정 없음" 안내 메시지 출력

Benchmark-1: 단순 프로젝트 (CLAUDE.md 1개, ~300 tokens)
  → 정상 분석 완료
  → "최적화 불필요" 보고
  → 중복 0건, 낭비 없음

Benchmark-2: pmo-vault (CLAUDE.md×4, rules×11, memory 대량)
  → 47%+ 낭비 감지
  → 중복 쌍 3건 이상 탐지
  → 트리거 추출 9/11건 이상

Benchmark-3: 복잡 프로젝트 (rules 20+)
  → 전체 5단계 파이프라인 완주
  → 10초 이내 완료 (성능 기준)
```

### 테스트 계층

```
Unit Tests
  → 각 pipeline 단계 독립 검증
  → adapter.list_sources() 빈 결과 처리
  → scorer 각 Tier 독립 동작

Integration Tests
  → Benchmark-0~3 E2E
  → 플랫폼별 어댑터 (claude_code, cursor, generic)

Property Tests
  → "빈 입력 → 크래시 없음" invariant
  → "총 토큰 = 소스별 합계" 정합성
```

---

## 10. 구현 로드맵

### Phase 1: CLI MVP (2주)

| Day | 작업 |
|---|---|
| 1 | Adapter 인터페이스 + 플랫폼 자동 감지 |
| 2 | Graceful degradation — 빈 프로젝트 처리 |
| 3 | TOKENIZE (token_usage 없으면 "데이터 없음" 안내) |
| 4 | INVENTORY — 전체 소스 열거 (없으면 빈 결과) |
| 5 | `ctxman init` / `scaffold` — 신규 사용자 진입점 |
| 6 | SCORE Tier 1+2 |
| 7~8 | TRIGGER 자동 추출 |
| 9 | DEDUP 신뢰도 기반 |
| 10 | SIMULATE + `ctxman verify` |
| 11 | events.jsonl 로깅 |
| 12 | CLI UX — Level별 출력 포맷 |
| 13 | E2E 검증: Benchmark-0 + Benchmark-2(pmo-vault) |
| 14 | README + PyPI 배포 |

### Phase 2: 정확도 개선 (4~6주)

- Perplexity 기반 Tier 3 스코어링 (claude-haiku API)
- `ctxman optimize --dry-run / --apply`
- `ctxman profile` (per-task 프로파일 관리)
- Web dashboard 초안

### Phase 3: 성능 + 확장 (3개월+)

- Rust 핵심 로직 포팅 (RTK처럼 단일 바이너리)
- Cursor / Copilot 어댑터 완성
- 클라우드 SaaS 검토 (Stars 1k 달성 후)

---

## 11. 기술 스택

| 영역 | 선택 | 근거 |
|---|---|---|
| CLI 프레임워크 | `typer` | Python-native, 자동 help 생성 |
| 토크나이저 | `tiktoken` | claude-3 호환, anthropic tokenizer fallback |
| 임베딩 | `sentence-transformers/all-MiniLM-L6-v2` | 빠름, 로컬 실행 |
| TF-IDF | `scikit-learn` | 표준, 의존성 최소 |
| 패키징 | `pyproject.toml` + PyPI | 표준 배포 |
| 언어 | Python 3.11+ | Phase 1 검증 속도 우선 |

---

## 12. 수익 모델 + 오픈소스 전략

- **Phase 1~2**: 완전 OSS (MIT 또는 Apache 2.0)
- **Stars 1k 달성 후**: Pro 모델 검토 (클라우드 분석 SaaS)
- **논문 병행**: SIOP 형식화 → 커뮤니티 신뢰도 + 채용 레버리지

---

## 13. 미해결 질문 (다음 논의)

1. OSS 완전 공개 vs PolyForm Noncommercial 중 어느 것?
2. 클라우드 분석 SaaS를 처음부터 설계에 포함할지?
3. SIOP 논문 공동 저자로 외부 연구자 포함할지?
4. pmo-vault 외 두 번째 실제 프로젝트(베타 고객) 확보 전략?
5. Cursor 어댑터 구현 방식 (hook 구조 차이 해소)?

---

## 관련 문서

| 문서 | 경로 |
|---|---|
| 연구 카탈로그 | `research/context-optimization-research.md` |
| 연구팀 토론 | `research/expert-team-discussion.md` |
| 창업팀 평가 | `research/startup-team-evaluation.md` |
| 양팀 개선안 | `research/improvement-plan.md` |
| 제로베이스 요구사항 | `research/zero-base-requirement.md` |
| 팀 레지스트리 | `research/teams.md` |
