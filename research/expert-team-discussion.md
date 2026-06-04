# 전문가 팀 심층 토론 결과

> 작성일: 2026-06-03
> 목적: Static Instruction Injection Optimization 연구 공백 검증 및 핵심 알고리즘 설계

---

## 팀 구성

| 역할 | 이름 | 전문 분야 |
|---|---|---|
| AI 연구원 1 | Dr. Kim | Prompt Compression / NLP (LLMLingua, NAACL) |
| AI 연구원 2 | Dr. Park | Agent Memory Architecture (ACON, Demand Paging) |
| AI 연구원 3 | Dr. Lee | Information Theory / Semantic Similarity |
| 연구소 총책임자 | Director Choi | 전략 방향·논문 기여 판단 |
| 아키텍처·개발 전문가 | Mr. Jung | 시스템 설계·구현 가능성 |

---

## 토론 1 — 문제 정의

**Dr. Kim:**
기존 prompt compression 연구(NAACL 2025 서베이, LoPace, LLMLingua-2)는 전부 동적 컨텐츠(대화 히스토리, RAG 문서, 도구 출력물) 대상. 세션 시작 전 고정으로 주입되는 instruction 파일을 압축 대상으로 명시한 논문은 단 한 편도 없음. 진짜 공백 확인.

**Dr. Park:**
Demand Paging 논문(arXiv 2603.09023)이 가장 근접. 857개 실제 프로덕션 세션 분석에서 전체 토큰의 **21.8%가 구조적 낭비**로 실측. 그 중 미사용 도구 스키마 11.0%, 불필요한 도구 결과 8.7%, 중복 콘텐츠 2.2%. 그러나 이 논문도 동적 페이징에 집중하고, 정적 config 파일 계층은 "L1 캐시"로 묶어 최적화 대상 바깥에 둠.

**Dr. Lee:**
정보이론 관점에서 현재 다중 rule 파일 주입은 **상호 정보량(mutual information)을 무시한 brute-force 주입**. cross-file redundancy를 탐지·제거하는 형식화된 방법론 없음. SemHash 같은 시맨틱 dedup 연구들은 학습 데이터 정제 용도이고 runtime instruction 파일 적용 사례 전무.

**Director Choi:**
세 분이 각기 다른 각도에서 같은 공백 확인. **"Multi-file Static Instruction Injection Optimization" 문제가 아직 형식화조차 안 됐음.** 단순한 tool 공백이 아니라 연구 문제 자체가 미정의된 상태.

---

## 토론 2 — 이론적 프레임워크

**Dr. Lee:**
가장 강력한 이론 기반은 **Rate-Distortion Theory 적용**. NeurIPS 2024 "Fundamental Limits of Prompt Compression"이 rate-distortion 프레임워크로 prompt compression의 이론적 한계를 정립. static instruction에 적용 시: *"작업 성능(distortion) δ를 허용할 때, N개 rule 파일의 최소 주입 토큰 수(rate)는 얼마인가?"*

**Dr. Kim:**
Selective Context 논문(arXiv 2304.12102)의 self-information 스코어링을 **cross-document importance ranking**으로 확장 가능. 여러 rule 파일에 걸쳐 어떤 문단이 작업 완수에 얼마나 기여하는지 측정.

**Dr. Park:**
Demand Paging 논문의 핵심 통찰 — *"LLM에서는 keeping이 비싸고 faulting이 싸다"* — 을 static config에 적용하면 수학적으로 lazy loading이 최적. ACON의 gradient-free guideline optimization 방법론을 rule 파일 선택 문제에 적용 가능: 어떤 rule을 로드했을 때 작업이 실패/성공했는지 피드백으로 압축 지침 반복 개선.

**Director Choi 정리 — 3개 이론 기반:**
1. **Rate-Distortion (NeurIPS 2024)** — 최적 압축의 이론적 하한
2. **Self-Information Scoring (Selective Context)** — 중요도 측정
3. **ACON의 Gradient-Free Guideline Optimization** — 피드백 기반 반복 개선

---

## 토론 3 — 핵심 알고리즘 설계

**Dr. Lee — 5단계 파이프라인:**
```
1. TOKENIZE: 각 rule 파일을 문단(chunk) 단위로 분할 후 토큰 수 계산
2. SCORE:    각 chunk의 self-information 점수 계산
             (소형 LM으로 perplexity 측정, 높은 perplexity = 정보 밀도 높음)
3. DEDUP:    문단 간 cosine similarity 계산 (sentence-transformers)
             similarity > 0.85: 중복 판정, 병합 제안
4. TRIGGER:  각 rule 파일에서 트리거 키워드 자동 추출
             (기존 트리거 섹션 파싱 + TF-IDF 상위 5개 자동 추출)
5. INDEX:    트리거→rule 매핑 인덱스 생성 (JSON)
```

**Dr. Kim — 3단계(DEDUP) 주의사항:**
instruction 파일은 의미론적으로 같아도 문맥이 달라야 하는 경우 있음 (예: secrets-query.md와 infrastructure-update.md의 배타 표 공유). 단순 cosine similarity 제거 대신 **쌍별 비교 후 병합 제안** 방식 필요.

**Dr. Park — Lazy Loading 핵심:**
트리거 인덱스 완성 후, 세션 시작 시 전체 rule 주입 대신 트리거 테이블만 주입. 실제 rule 내용은 LLM이 해당 키워드를 감지할 때 on-demand 로드. johnlindquist 실험에서 이 방법만으로 54% 감소. **자동화하면 수동 트리거 관리 불필요.**

**Mr. Jung — 아키텍처 분리:**
```
Offline:  [Analyzer] → [index.json + compressed_rules/] 생성
Runtime:  [Loader]   → index.json 읽어서 CLAUDE.md에 트리거 테이블만 주입
                     → rule 내용은 .claude/rules/lazy/ 에 대기
```
Python CLI로 시작, 이후 Rust 포팅 가능 구조로 설계.

---

## 최종 결론

### 연구 공백 정의 (합의)

```
문제명: Static Instruction Injection Optimization Problem (SIOP)

정의: M개의 작업 유형이 있을 때, N개 rule 파일 집합에서
      작업 성능 δ를 유지하면서 주입 토큰을 최소화하는
      per-task 최적 subset을 자동으로 발견하는 문제.
```

**공백 근거:**
- 기존 압축 연구 100%가 동적 컨텐츠 대상 (정적 config 미다룸)
- Demand Paging 논문 - 구조적 낭비 21.8% 실측했으나 static 계층 제외
- 트리거 기반 lazy loading - 실험적 증명됐으나 미형식화·미자동화
- Cross-file dedup - 학습 데이터 전처리 외 적용 전무

### 핵심 알고리즘 스택 (우선순위 순)

| 순서 | 이름 | 방법 | 기반 연구 |
|---|---|---|---|
| 1 | Token Accounting | 현황 측정 | Rate-Distortion 기준점 |
| 2 | Trigger Auto-Extraction | TF-IDF + 섹션 파싱 | johnlindquist 54% 자동화 |
| 3 | Cross-File Dedup | Sentence-Transformers cosine similarity | SemHash, D4 |
| 4 | Importance Scoring | Self-information 기반 chunk 우선순위 | Selective Context |
| 5 | Profile Generation | 위 4개 결과로 per-task 프로파일 자동 생성 | ACON 방식 |
| 6 | Feedback Loop | Gradient-free 반복 개선 (Phase 2) | ACON |

### 도구 포지셔닝

```
RTK:          shell output 압축   ← 다른 레이어 (39k stars)
context-mode: tool output 샌드박스 ← 다른 레이어 (16k stars)
이 도구:      static config 최적화 ← 아무도 없는 레이어 (공백)
```

**논문화 가능성:** *"STATIC: Static Instruction Compression for Multi-Rule LLM Agent Configurations"*
기여: (1) SIOP 문제 형식화, (2) 자동 트리거 추출 알고리즘, (3) cross-file semantic deduplication

---

## 참고 논문

| 논문 | 링크 |
|---|---|
| Demand Paging for LLM Context Windows (2026.03) | https://arxiv.org/abs/2603.09023 |
| Prompt Compression Survey NAACL 2025 | https://arxiv.org/html/2410.12388v2 |
| Fundamental Limits of Prompt Compression NeurIPS 2024 | https://openreview.net/forum?id=TeBKVfhP2M |
| Learning to Configure Agentic AI Systems | https://arxiv.org/pdf/2602.11574 |
| Selective Context / Self-Information | https://arxiv.org/pdf/2304.12102 |
| ACON | https://arxiv.org/abs/2510.00615 |
| LoPace Lossless Compression | https://arxiv.org/pdf/2602.13266 |
