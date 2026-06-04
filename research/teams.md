# 프로젝트 팀 구성 레지스트리

> 작성일: 2026-06-03
> 용도: 재소환 가능한 팀 구성 레퍼런스
> 프로젝트: rune — Static Instruction Injection Optimizer

---

## Team A: AI 연구팀 (Research Team)

**목적:** 연구 공백 검증, 알고리즘 설계, 논문 방향 결정

| 역할 | 이름 | 전문 분야 | 관점 |
|---|---|---|---|
| AI 연구원 1 | **Dr. Kim** | Prompt Compression / NLP | LLMLingua, NAACL 서베이, 토큰 압축 기법 |
| AI 연구원 2 | **Dr. Park** | Agent Memory Architecture | ACON, Demand Paging, 에이전트 히스토리 관리 |
| AI 연구원 3 | **Dr. Lee** | Information Theory / Semantic Similarity | Rate-Distortion, self-information, cross-file dedup |
| 연구소 총책임자 | **Director Choi** | 전략 방향·논문 기여 판단 | 연구 공백 종합 평가, 기여 가치 판단 |
| 아키텍처·개발 전문가 | **Mr. Jung** | 시스템 설계·구현 가능성 | Offline/Runtime 분리, Python→Rust 포팅 전략 |

**재소환 시 사용법:**
> "Research Team(Dr. Kim, Dr. Park, Dr. Lee, Director Choi, Mr. Jung)을 소환해서 [주제]에 대해 논의해줘"

**지금까지 다룬 주제:**
- 연구 공백 정의 (SIOP 문제 형식화)
- 이론적 프레임워크 (Rate-Distortion, Self-Information, ACON)
- 핵심 알고리즘 5단계 파이프라인 설계
- 논문화 가능성 및 제목 초안

---

## Team B: 창업팀 (Startup Team)

**목적:** 사업 가능성 평가, 제품 로드맵, 구현 계획

| 역할 | 이름 | 관점 |
|---|---|---|
| CEO | **Alex** | 시장 기회·사업 모델·투자 가능성·Go-to-market |
| CTO | **Ray** | 기술 실현 가능성·스택 선택·확장성·리스크 |
| PO (Product Owner) | **Sam** | 사용자 니즈·UX·제품 로드맵·PMF |
| PL (Project Lead) | **Dana** | 구현 타임라인·리소스 배분·의존성 리스크 |

**재소환 시 사용법:**
> "Startup Team(CEO Alex, CTO Ray, PO Sam, PL Dana)을 소환해서 [주제]에 대해 평가해줘"

**지금까지 다룬 주제:**
- 시장 실재성 검증 (RTK/context-mode 사례 기반)
- 기술 스택 결정 (Python → Rust, typer, sentence-transformers)
- 사용자 페르소나 3종 정의
- 제품 로드맵 v0.1~v1.0
- Phase 1 구현 계획 (2주, Day별 일정)
- **최종 판정: GO ✅**

---

## 양 팀 합의 사항 (Cross-Team)

| 항목 | 결론 |
|---|---|
| 문제명 | Static Instruction Injection Optimization Problem (SIOP) |
| 포지셔닝 | RTK(tool output) · context-mode(tool output) 와 다른 레이어 — 정적 config 레이어 독점 |
| Phase 1 범위 | `rune analyze` — 측정·시각화만 (optimize는 Phase 2) |
| 제품명 | `rune` (MVP), 성장 후 재브랜딩 옵션 |
| 알고리즘 우선순위 | Token Accounting → Trigger Extraction → Cross-File Dedup → Importance Scoring → Profile Generation |
| 구현 언어 | Python 3.11+ (Phase 1), Rust 포팅 (Phase 3) |
| 수익 모델 | 완전 OSS로 시작, Stars 1k 후 Pro 검토 |
| 논문 가능성 | ✅ SIOP 형식화 + 자동 트리거 추출 + cross-file dedup |

---

## 미해결 질문 (다음 팀 소환 시 논의 주제)

1. OSS 완전 공개 vs PolyForm Noncommercial 중 어느 것?
2. 클라우드 분석 SaaS를 처음부터 설계에 포함할지?
3. SIOP 논문 공동 저자로 외부 연구자 포함할지?
4. pmo-vault 외 두 번째 실제 프로젝트(베타 고객) 확보 전략?
5. Cursor 어댑터 구현 방식 (hook 구조 차이 해소)?

---

## 관련 문서

- `context-optimization-research.md` — 논문·기법 카탈로그
- `expert-team-discussion.md` — Research Team 전체 토론 기록
- `startup-team-evaluation.md` — Startup Team 전체 평가 기록
