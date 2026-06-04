# LLM Context Optimization 연구 자료

> 작성일: 2026-06-03
> 목적: Claude Code 세션 컨텍스트 압축 최적화 앱 설계를 위한 선행 연구

---

## 1. 핵심 원칙

> **예방(Prevention) > 압축(Compression)**
> 불필요한 토큰을 처음부터 주입하지 않는 것이 최고의 최적화다. (Morph 2026)

---

## 2. 학술 논문

### ACON: Optimizing Context Compression for Long-horizon LLM Agents
- **출처**: arXiv 2510.00615, KAIST + Microsoft (2025.10)
- **링크**: https://arxiv.org/abs/2510.00615
- **핵심 기여**: 에이전트의 누적 히스토리 압축을 3방향으로 분리하는 통합 프레임워크
- **3가지 압축 방향**:
  1. **히스토리 압축** — 누적 액션/관찰 기록이 임계값 초과 시 요약
  2. **관찰 압축** — 최신 환경 반환값이 임계값 초과 시 압축
  3. **가이드라인 최적화** — 실패 사례 분석으로 압축 지침 반복 개선 (gradient-free)
- **성과**: 피크 토큰 26-54% 감소, 증류 시 95%+ 정확도 유지, 소규모 모델 성능 20-46% 향상
- **특장점**: gradient-free → 클로즈드소스 API 모델(Claude 포함)에 직접 적용 가능

### LLMLingua / LLMLingua-2
- **출처**: Microsoft Research
- **링크**: https://www.microsoft.com/en-us/research/blog/llmlingua-innovating-llm-efficiency-with-prompt-compression/
- **LLMLingua**: perplexity 점수로 개별 토큰 평가 → 저중요 토큰 제거
- **LLMLingua-2**: 토큰별 yes/no 분류를 병렬 처리 (XLM-RoBERTa-large 인코더 사용)
  - 기존 대비 3x-6x 속도 향상
  - 최대 20x 압축 (자연어 기준)
- **주의**: 코드/구조화 데이터에는 토큰 단위 제거가 구문을 깰 수 있음 → chunk-level 필요

### QwenLong-CPRS
- **출처**: arXiv 2505.18092 (2025.05)
- **링크**: https://arxiv.org/html/2505.18092v1
- **방법**: 동적 컨텍스트 최적화 (Dynamic Context Optimization)
- **성과**: RAG 베이스라인 대비 97.3% 압축, 128K 입력에서 3.47x 가속

### Selective Context (자기정보 기반 필터링)
- **출처**: arXiv 2304.12102
- **링크**: https://arxiv.org/pdf/2304.12102
- **방법**: LM의 self-information(자기정보)으로 각 어휘 단위 중요도 계산 → 저정보 콘텐츠 필터링
- **특징**: 별도 학습 불필요, 베이스 LM만으로 동작

### Provence: Efficient and Robust Context Pruning for RAG
- **출처**: arXiv 2501.16214
- **링크**: https://arxiv.org/pdf/2501.16214
- **방법**: RAG 파이프라인 특화 컨텍스트 가지치기
- **성과**: ICLR 2025 채택

---

## 3. 실전 기법 카탈로그

### 3.1 Verbatim Compaction
- **제공**: Morph (https://www.morphllm.com/prompt-compression)
- **방법**: 저신호 토큰 완전 삭제 (출력 = 입력의 부분집합)
- **성과**: 98% 정확도, 3,300+ tok/s, 환각 위험 0%
- **압축률**: 50-70% (공격적이지 않은 편)
- **적합**: 코딩 에이전트, 정확한 파일 경로 보존 필요한 경우

### 3.2 Token-Level Pruning (LLMLingua)
- **방법**: perplexity 점수로 개별 토큰 평가
- **성과**: 최대 20x 압축, 1.7x-5.7x 속도 향상
- **주의**: 코드 구문 손상 위험 (연산자·괄호 제거 가능)
- **적합**: 자연어 추론, RAG 프롬프트

### 3.3 Observation Masking (JetBrains 방식)
- **방법**: 이전 도구 출력을 플레이스홀더로 교체, 작업 기록만 유지
- **성과**: 60-80% 감소, 추가 계산 비용 0원
- **단점**: 이전 출력 재참조 시 재검색 필요
- **적합**: 일회성 도구 출력, 에이전트 행동 추적

### 3.4 Adaptive Compaction (ACON 방식)
- **방법**: 컨텍스트 세그먼트별 다른 압축 수준 적용
- **성과**: 26-54% 감소, 95%+ 정확도 유지
- **적합**: 혼합 콘텐츠 타입을 가진 에이전트

### 3.5 Prevention-First (WarpGrep + Fast Apply)
- **방법**: 스니펫 검색 + 컴팩트 diff로 불필요한 토큰 원천 차단
- **성과**: 3-4배 토큰 소비 감소, 압축 필요 빈도 3-4배 감소
- **적합**: 장기 에이전트 세션

### 3.6 Hybrid Prevention-First (FlashCompact)
- **방법**: 검색 최적화 + 컴팩트 쓰기 + 잔여 정리
- **성과**: SWE-Bench Pro 최고 성능, 1-2회 압축만 필요
- **적합**: 종합 컨텍스트 효율성 필요

---

## 4. Claude Code 특화 사례

### johnlindquist: 54% 토큰 감소 (7,584 → 3,434 토큰)
- **출처**: https://gist.github.com/johnlindquist/849b813e76039a908d962b2f0923dc9a
- **핵심 인사이트**: "Claude는 상세한 문서를 미리 볼 필요 없다. 언제 로드할지 알기 위한 트리거만 필요하다."
- **기법**:
  1. **트리거 기반 라우팅**: 상세 설명 대신 트리거 키워드 목록만 초기 주입
  2. **Lazy Loading**: `Skill("name")` 호출로 필요 시 상세 문서 로드
  3. **파일 통합**: identity + simulator-paradigm 합치기 → 82% 감소
  4. **레지스트리 중앙화**: `skills-rules.md`를 트리거 테이블로 압축 → 70% 감소
  5. **컨텍스트 플러딩 방지**: 중복 주입 규칙 제거

### Claude Code 시스템 프롬프트 구조 분석
- **출처**: https://www.dbreunig.com/2026/04/04/how-claude-code-builds-a-system-prompt.html
- **CLAUDE.md 주입 방식**: system prompt가 아닌 `<system-reminder>` 태그로 메시지 배열에 삽입
- **tools 정의**: 50개+ 도구, 조건부 로딩
- **압축 방식**: 약 12가지 방법으로 대화 기록 요약·오프로딩

---

## 5. 알고리즘 분류 매트릭스

| 알고리즘 | 타입 | 압축률 | 환각 위험 | 코드 안전성 | API 호환 |
|---|---|---|---|---|---|
| Verbatim Compaction | 삭제 | 50-70% | 없음 | 높음 | O |
| Token-Level (LLMLingua) | 삭제 | 최대 95% | 낮음 | 낮음 | O |
| Chunk-Level Pruning | 삭제 | 30-60% | 낮음 | 높음 | O |
| Observation Masking | 치환 | 60-80% | 없음 | 높음 | O |
| Summarization (LLM) | 재작성 | 70-90% | 있음 | 보통 | O |
| ACON Adaptive | 혼합 | 26-54% | 낮음 | 높음 | O |
| Prevention-First | 구조적 | 75%+ | 없음 | 높음 | O |
| Lazy Loading (트리거) | 구조적 | ~54% | 없음 | 높음 | O |

---

## 6. pmo-vault 적용 분석

### 현재 주입 구조 (문제)
```
세션 시작 시 주입:
├── CLAUDE.md × 4개 (global + workspace + project + vault)
├── rules/*.md × 11개 (총 1,775줄)
│   ├── document-convention.md    304줄
│   ├── lint-vault.md             245줄
│   ├── linear-usage.md           215줄
│   ├── infrastructure-update.md  196줄
│   ├── onsite-schedule-lookup.md 182줄
│   ├── points-management.md      168줄
│   └── ... 5개 추가
├── Skills 목록 100+개
├── recent context (claude-mem, ~110k tokens 참조)
└── Deferred tools 150+개
```

### 권장 최적화 전략 (연구 기반)

**우선순위 1 — Prevention (트리거 기반 Lazy Loading)**
- rules 11개를 트리거 테이블로 교체 (전체 내용 미주입)
- 트리거 키워드 감지 시 해당 rule만 on-demand 로드
- 예상 절감: 70-80% (johnlindquist 사례 기준)

**우선순위 2 — Verbatim Compaction**
- rules 내 중복 문장, 예시 중복, 반복 설명 제거
- 환각 위험 없음, 코드 안전
- 예상 절감: 30-50%

**우선순위 3 — Chunk-level Semantic Deduplication**
- rules 간 교차 중복 탐지 (예: secrets-query와 infrastructure-update의 키워드 배타 표)
- 중복 섹션 통합 또는 참조로 대체
- 예상 절감: 20-40%

**우선순위 4 — Profile-based Loading**
- 작업 유형별 프로파일 (`weekly-report`, `onsite`, `incident`, `default`)
- 각 프로파일: 해당 작업에 필요한 rules subset만 로드
- ACON의 "세그먼트별 다른 압축 수준" 아이디어 적용

---

## 7. 기존 도구 및 라이브러리

| 도구 | 용도 | 링크 |
|---|---|---|
| LLMLingua | 토큰 레벨 압축 Python 라이브러리 | microsoft/LLMLingua |
| LlamaIndex LongLLMLingua | RAG 특화 압축 | llamaindex.ai |
| Redis LangCache | 시맨틱 캐싱 레이어 | redis.io |
| tiktoken | OpenAI 토크나이저 (토큰 계산) | openai/tiktoken |
| anthropic tokenizer | Claude 토큰 계산 | anthropic SDK |

---

## 8. 참고 링크

- [ACON paper](https://arxiv.org/abs/2510.00615)
- [Claude Code 54% reduction gist](https://gist.github.com/johnlindquist/849b813e76039a908d962b2f0923dc9a)
- [Prompt Compression 8 Techniques (Morph)](https://www.morphllm.com/prompt-compression)
- [Context Pruning (Redis)](https://redis.io/blog/context-pruning-llm-tokens/)
- [LLMLingua (Microsoft)](https://www.microsoft.com/en-us/research/blog/llmlingua-innovating-llm-efficiency-with-prompt-compression/)
- [How Claude Code Builds a System Prompt](https://www.dbreunig.com/2026/04/04/how-claude-code-builds-a-system-prompt.html)
- [QwenLong-CPRS](https://arxiv.org/html/2505.18092v1)
- [Context Optimization Framework (Medium 2026)](https://luharuka.medium.com/context-optimization-a-comprehensive-framework-for-reducing-large-language-model-token-usage-fed8d9229e30)
- [LongLLMLingua (LlamaIndex)](https://www.llamaindex.ai/blog/longllmlingua-bye-bye-to-middle-loss-and-save-on-your-rag-costs-via-prompt-compression-54b559b9ddf7)
- [CCF: Context Compression Framework](https://arxiv.org/html/2509.09199v1)
