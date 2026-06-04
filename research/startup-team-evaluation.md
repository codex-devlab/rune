# 창업팀 평가 — SIOP 기반 Context Optimizer

> 작성일: 2026-06-03
> 근거 자료: context-optimization-research.md, expert-team-discussion.md
> 평가 대상: Static Instruction Injection Optimization 도구 창업 가능성

---

## 팀 구성

| 역할 | 이름 | 관점 |
|---|---|---|
| CEO | Alex | 시장 기회·사업 모델·투자 가능성 |
| CTO | Ray | 기술 실현 가능성·스택 선택·확장성 |
| PO | Sam | 사용자 니즈·제품 로드맵·PMF |
| PL | Dana | 구현 타임라인·리소스·리스크 |

---

## 라운드 1 — 시장 기회 평가

### CEO Alex

**결론: 시장 실재성 ✅, 규모 불확실 ⚠️**

RTK가 39~51k stars를 얻은 건 "Claude Code 사용자가 토큰 비용에 민감하다"는 걸 증명합니다. context-mode 16k stars도 같은 신호. 그런데 두 도구 모두 **tool output 레이어**만 건드립니다. 정적 config 레이어에 아무도 없다는 건 블루오션이거나 — 수요가 없는 곳이라는 뜻일 수도 있습니다.

수요 검증 필요 질문:
- Claude Code heavy user들이 실제로 CLAUDE.md/rules 비대화를 문제로 인식하는가?
- 현재 수동으로 어떻게 해결하고 있는가? (없으면 pain point 아닌 것)

**시장 추정 (보수적):**
- Claude Code MAU: ~500k+ (2026 기준 추정)
- 그 중 multi-rule 프로젝트 운영: ~15% = 75k 사용자
- 유료 전환 가능(월 $5): ~5% = 3,750명 → MRR $18,750
- 도구 생태계 확장 시: Cursor/Copilot 포함 3-5x

**사업 모델 옵션:**
1. OSS Core + Pro 클라우드 (Token Optimizer 모델, PolyForm)
2. 완전 OSS (RTK 모델 → 컨설팅·기업 지원으로 수익)
3. API SaaS (분석 서비스 구독)

**CEO 권고:** Phase 1은 완전 OSS로 community traction 먼저. Stars 1k 넘으면 Pro 모델 검토.

---

### CTO Ray

**결론: 기술 실현 가능성 ✅, 핵심 리스크 2개 ⚠️**

알고리즘 스택 5개 중 4개는 기존 라이브러리로 구현 가능합니다:

```
Token Accounting     → tiktoken + anthropic SDK (trivial)
Trigger Extraction   → regex 파싱 + scikit-learn TF-IDF (2일)
Cross-File Dedup     → sentence-transformers/all-MiniLM-L6-v2 (3일)
Importance Scoring   → perplexity 계산, GPT2-small 또는 claude-haiku API (1주)
Profile Generation   → 위 4개 결과 집계 로직 (3일)
```

**리스크 1: 중요도 스코어링의 정확도**
perplexity 기반 self-information 스코어링은 *단일 문서 내*에서는 잘 작동하지만, rule 파일처럼 **도메인 특화된 instruction 텍스트**에서는 일반 LM의 perplexity가 실제 중요도와 다를 수 있습니다. 예를 들어 "이 룰을 위반하면 lint가 깨진다"는 문장은 pmo-vault 맥락에선 중요하지만, GPT2의 perplexity로는 "평범한 문장"으로 평가될 수 있습니다.

→ **해결 방향:** 스코어링에 두 신호를 결합. (a) perplexity 기반 언어 모델 스코어 + (b) 섹션 헤더·볼드·트리거 마커 등 구조적 신호. 구조적 신호는 도메인 무관하게 안정적.

**리스크 2: Lazy Loading의 LLM 협력 의존성**
트리거 테이블만 주입하고 rule 내용을 on-demand 로드하는 방식은 **LLM이 트리거를 올바르게 인식하고 로드 요청을 해야** 작동합니다. Claude Code의 경우 system-reminder 구조 덕분에 hook을 통해 강제 주입이 가능하지만, 다른 에이전트(Cursor, Copilot)는 hook 구조가 다를 수 있습니다.

→ **해결 방향:** Adapter 패턴으로 플랫폼별 주입 방식 분리. Claude Code는 hook 기반, 나머지는 CLAUDE.md/설정 파일 직접 수정 방식.

**기술 스택 권고:**
```
Phase 1 (CLI):   Python 3.11+, typer, sentence-transformers, tiktoken
Phase 2 (Web):   FastAPI backend + React/Next.js dashboard
Phase 3 (성능):  Rust 핵심 로직 포팅 (RTK처럼 단일 바이너리)
```

**CTO 권고:** Phase 1을 Python으로 빠르게 검증. perplexity 스코어링은 claude-haiku API 사용해서 정확도를 먼저 검증하고 나서 경량 모델로 대체.

---

### PO Sam

**결론: PMF 가능 ✅, 온보딩 경험이 성패 결정 ⚠️**

**사용자 페르소나 분석:**

**페르소나 A: Power User Dev (메인 타겟)**
- Claude Code를 매일 사용하는 개발자
- 이미 컨텍스트 압축을 경험하고 짜증을 느낌
- `ctxman analyze` 실행 → "내 프로젝트에서 47% 낭비 중" → 즉시 가치 체감
- RTK, context-mode를 이미 사용 중 → 이 계층은 인식하지만 도구가 없어서 손으로 관리

**페르소나 B: Team/Org Admin**
- 여러 명이 사용하는 pmo-vault 같은 공유 vault 관리자
- rules 파일이 팀 전체에 영향 → 최적화 효과가 팀 전체에 전파
- 대시보드·리포트 필요 (Web Phase에서 해소)

**페르소나 C: Researcher / Tinkerer**
- SIOP 논문 읽고 관심 가진 연구자
- 벤치마크·재현 가능 실험 필요
- GitHub Star 기여자

**핵심 UX 원칙 (RTK 성공에서 배운 것):**
> "설치하면 30초 안에 측정 가능한 숫자가 나와야 한다."

```bash
# 이 경험이 첫 인상을 결정
pip install ctxman
ctxman analyze .

# 출력:
📊 Context Analysis Report
─────────────────────────────────────
총 주입 토큰: 8,432
├── CLAUDE.md × 4:      2,103 (24.9%)
├── rules × 11:         3,891 (46.2%)  ← 🔴 최대 낭비원
├── Skills 목록:         1,204 (14.3%)
└── Memory 참조:         1,234 (14.6%)

중복 탐지: 3쌍 (추정 절감 892 tokens)
트리거 추출 가능: 11개 rule 중 9개

예상 최적화 후: 4,201 tokens (-50.2%)

실행: ctxman optimize --preview
```

**Product Roadmap:**
```
v0.1 (2주): analyze 명령만. 측정 + 시각화.
v0.2 (4주): optimize --dry-run. 변경 preview, 승인 후 적용.
v0.3 (6주): profile 명령. per-task 프로파일 생성·전환.
v0.5 (3개월): watch 명령. 세션 모니터링 + 압축 트리거 알림.
v1.0 (6개월): Web dashboard. 팀/Org 레벨 분석.
```

**PO 권고:** v0.1에서 "analyze만" 출시. 측정 가치만으로도 충분히 바이럴 가능 (RTK처럼 "X% 낭비 중!" 스크린샷 공유).

---

### PL Dana

**결론: 실행 가능 ✅, Phase 1은 1인 2주 가능 ⚠️**

**Phase 1 구현 계획 (2주, 1명):**

```
Day 1-2:  프로젝트 스캐폴딩
          - pyproject.toml, typer CLI 뼈대
          - adapter 인터페이스 정의 (claude_code, cursor, generic)
          - 테스트 픽스처 준비 (pmo-vault 실제 데이터)

Day 3-4:  Token Accounting
          - tiktoken + anthropic 토크나이저 통합
          - CLAUDE.md, rules/, skills/ 파싱
          - 소스별 토큰 수 집계 + JSON 출력

Day 5-6:  Trigger Extraction
          - rule 파일 내 "트리거 키워드" 섹션 regex 파싱
          - fallback: TF-IDF 상위 5개 자동 추출
          - trigger_index.json 생성

Day 7-8:  Cross-File Dedup
          - sentence-transformers 임베딩
          - pairwise cosine similarity 계산
          - 중복 쌍 리포트 (자동 제거 아닌 제안만)

Day 9-10: Importance Scoring (간소화 버전)
          - 구조적 신호: 헤더 레벨, 볼드, 트리거 마커 가중치
          - perplexity는 Phase 2로 연기 (API 비용·지연 회피)
          - chunk별 점수 → 최적화 후 예상 토큰 계산

Day 11-12: CLI UX 완성
          - ctxman analyze: 풀 리포트
          - ctxman analyze --json: 파이프라인 통합용
          - 컬러 출력, 진행 바

Day 13-14: 테스트 + README + 첫 릴리즈
          - pmo-vault 실 데이터로 E2E 검증
          - GitHub 공개 + PyPI 배포
          - HackerNews/Reddit 공유용 데모 GIF
```

**의존성 리스크:**
| 의존성 | 리스크 | 대안 |
|---|---|---|
| sentence-transformers | 모델 다운로드 첫 실행 느림 | --no-semantic 플래그로 TF-IDF만 사용 |
| tiktoken | OpenAI 라이선스 제약 | anthropic SDK tokenizer 또는 직접 구현 |
| claude-haiku API (perplexity) | 비용 발생 | Phase 2로 연기, 구조적 신호로 대체 |

**PL 권고:** Day 9-10 perplexity 스코어링을 Phase 2로 미루고, 구조적 신호 기반 간소화 버전으로 Phase 1 완성. 출시 우선, 정확도는 데이터 모은 후 개선.

---

## 최종 평가 테이블

| 평가 항목 | CEO | CTO | PO | PL | 종합 |
|---|---|---|---|---|---|
| 시장 실재성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 기술 실현 가능성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PMF 가능성 | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| 경쟁 차별성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 실행 속도 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 수익화 명확성 | ⚠️ | — | ⚠️ | — | ⚠️ |
| 논문/학술 가치 | ✅ | ✅ | — | — | ✅ |

---

## 팀 합의 결론

### Go / No-Go: **GO** ✅

**근거:**
1. **시장 공백 실재** — RTK·context-mode가 증명한 시장에서 아무도 없는 레이어
2. **2주 MVP 가능** — 기존 라이브러리로 Phase 1 단독 구현 현실적
3. **즉시 측정 가능한 가치** — "X% 낭비 중" 숫자 하나로 바이럴 가능
4. **논문 가치 병행** — SIOP 형식화는 커뮤니티 신뢰도 + 채용 레버리지

### 전제 조건 (Must-have before launch)
- pmo-vault 실 데이터로 "Before/After 50%+ 절감" 검증 완료
- analyze 명령 UX가 RTK 수준의 임팩트 있는 숫자 출력
- Claude Code 외 1개 플랫폼 어댑터 (Cursor) Phase 1 포함

### 즉시 실행 액션

```
Week 1: CTO(Ray) + PL(Dana) → Python CLI Phase 1 구현
         PO(Sam) → 랜딩 페이지 초안 + HN 포스트 초안
         CEO(Alex) → RTK/context-mode 커뮤니티 리서치, 잠재 얼리어답터 인터뷰 5명

Week 2: 코드 완성 → pmo-vault E2E 검증
         README + 데모 GIF + Before/After 숫자 확정
         GitHub 공개 + PyPI + HN 포스팅

Week 3+: 피드백 수집 → v0.2 scope 확정
```

### 제품명 후보

| 이름 | 장점 | 단점 |
|---|---|---|
| **ctxman** | 직관적, CLI 친화적 | 평범함 |
| **staticx** | STATIC 논문 브랜딩 | 발음 어색 |
| **rulefold** | rule 압축 의미 명확 | 좁은 의미 |
| **prism** | 분석·분리 의미, 멋짐 | 중복 가능성 |
| **lumen** | 빛=명료화, 좋은 의미 | 기술과 거리 |

→ **추천: `ctxman`** (MVP 단계), 성장 후 재브랜딩 옵션 열어둠

---

## 미해결 질문 (다음 세션 논의)

1. 오픈소스 완전 공개 vs PolyForm Noncommercial (Token Optimizer 모델) 중 어느 것?
2. 클라우드 분석 SaaS를 처음부터 설계에 포함할지?
3. SIOP 논문 공동 저자로 외부 연구자 포함할지?
4. pmo-vault 외 두 번째 실제 프로젝트(베타 고객) 확보 전략?
