# Claude 모델 선택 가이드 — dev 단계별

> dev-plugin 의 4단계 개발 사이클(설계 · 개발 · 테스트 · 리팩토링)에서
> 각 단계에 가장 적합한 Claude 모델을 고르는 실무 가이드.
> 목표: **품질을 희생하지 않으면서 토큰 비용을 최소화**.

## 전제

- 가용 모델: **Opus** (`opus`) / **Sonnet** (`sonnet`) / **Haiku** (`haiku`)
- 상대 비용(러프): Opus ≈ 5× Sonnet ≈ 15× Haiku
- 상대 품질(러프): Opus > Sonnet > Haiku, 다만 **단계 특성에 따라 Sonnet/Haiku 로도 동일 품질 달성 가능**
- 1M context 모드(Opus 전용)는 약 2× 추가 가산 — 대형 레거시 분석이 아닌 신규 개발에는 불필요

---

## TL;DR

| 단계 | 권장 모델 | 한 줄 이유 |
|---|---|---|
| **1. 설계** (dev-design) | **Sonnet** | 판단이 필요하지만 Opus만큼의 깊은 추론은 대부분 불필요. Haiku는 금지(설계 실수 파급력 최대). |
| **2. 개발** (dev-build) | **Sonnet** | 패턴 기반 코드 생성. 토큰 소비가 가장 커서 절감 효과 큼. |
| **3. 테스트** (dev-test) | **Haiku** | 기계적 실패-분석-수정 루프. 속도·비용 모두 최적. |
| **4. 리팩토링** (dev-refactor) | **Sonnet** | "언제 멈출지 아는" 균형 감각이 가장 중요. Opus는 과도, Haiku는 부족. |

> **한 줄 기억**: 설계·개발·리팩토링은 Sonnet, 테스트는 Haiku. 문제 생기면 그 Task만 한 단계 올린다.

---

## 1. 설계 — `dev-design`

### 무엇을 하는가
PRD/TRD를 읽고 Task 의 구현 전략·자료구조·파일 구조·수락 기준을 `design.md` 에 문서화.

### 권장: **Sonnet**

**근거**:
- 대량 context 읽기(PRD 수십~수백 KB + TRD + 관련 코드) → Sonnet 200K context 로 충분
- 판단이 필요한 작업 (DB 스키마 결정, 테이블 관계, API 경로 구조, 상태 머신 전이 등)
- Opus 수준의 깊은 추론은 대부분 불필요 — 설계 문서는 "합리적 기본값"을 고르는 작업이지 논문이 아님

### ❌ Haiku 금지

- Haiku는 복잡한 문서를 "대충 훑고 넘어가는" 경향
- 설계 단계 실수는 이후 3단계(build/test/refactor)를 통째로 오염 → **절감액이 가장 작고 복구 비용이 가장 큰 단계**
- 사례: Haiku 가 멀티테넌시 격리 방식을 잘못 판단 → build 에서 RLS 누락 → test 통과 → 실전에서 데이터 유출

### ⬆ Opus 로 올려야 할 신호

- 분산 트랜잭션·보안 경계·복잡한 상태 머신 설계
- "여러 정답 중 trade-off 선택이 매우 중요한" 순간
- 설계 문서 자체의 길이가 수천 줄을 넘거나, 크로스 레이어 영향 분석이 필요
- 예시: OAuth 플로우 설계, 이벤트 소싱 선택, 샤딩 전략

### 체크리스트
- [ ] Sonnet 기본
- [ ] 보안/동시성/분산 경계가 포함된 Task 만 선택적 Opus
- [ ] 절대 Haiku 사용 금지

---

## 2. 개발 — `dev-build`

### 무엇을 하는가
`design.md` 기반으로 테스트 먼저 작성 → 구현 → 테스트 통과까지 (TDD).

### 권장: **Sonnet**

**근거**:
- 가장 긴 단계 (라인 수 기준) → 토큰 소비가 큼 → **절감 효과가 큰 곳**
- "설계 문서대로 코드 생성"은 강한 추론보다는 패턴 적용·문법 정확성이 핵심
- Sonnet 은 TypeScript · Drizzle · tRPC · Vitest · Next.js · Fastify 등 현대 스택에 충분히 숙련
- Opus 는 오버킬 — 같은 코드를 더 비싸게 만들 뿐

### ⬇ Haiku 로 다운그레이드 가능한 경우

- **단순 CRUD + 강한 타입 가드가 있는 프레임워크**
  - 예: Drizzle 스키마 한 파일, tRPC 프로시저 단순 조회
- 테스트 케이스가 명확하고 로직이 10~20줄 수준
- 주의: **Haiku 가 미묘한 null/undefined 처리·에러 바운더리를 놓쳐 test 단계에서 재시도가 누적되면 Sonnet 보다 비싸질 수 있음**

### ⬆ Opus 로 올려야 할 신호

- 복잡한 비즈니스 규칙 (예: 배송비 계산, 재고 락, FSM 전이)
- 여러 레이어를 가로지르는 동시성 제어
- 대부분의 Phase 1 범위에서는 **거의 해당 없음**

### 체크리스트
- [ ] Sonnet 기본
- [ ] 순수 CRUD Task 에서만 Haiku 실험 (test 재시도 누적 모니터링)
- [ ] Opus 는 복잡한 비즈니스 로직 전용

---

## 3. 테스트 — `dev-test` ⭐

### 무엇을 하는가
전체 테스트 실행 → 실패 로그 읽기 → 원인 국소화 → 1~5줄 수정 → 재실행. 최대 3회 반복.

### 권장: **Haiku**

**근거** (이 단계가 절감 효과 최대):
- **가장 기계적인 루프**: "에러 메시지 파싱 → stack trace 에서 파일·라인 특정 → 타입 오류 수정 / assertion 고치기". 창의성 0%.
- Haiku 는 test output 파싱·단순 패치 적용에 매우 빠르고 정확
- **재시도 루프라 속도가 비용에 직접 영향**: Haiku 가 한 사이클에 ~4초 vs Sonnet ~12초 → 동일 시간 내 3배 많은 시도 가능
- Opus 대비 ~15×, Sonnet 대비 ~3× 저렴

### ⬆ Sonnet 으로 올려야 할 신호

- **같은 실패를 3회 연속 같은 방식으로 고치려 드는 경우** → 근본 원인을 못 짚고 있음 → Sonnet 이 한 단계 물러서서 분석 필요
- **경계 교차 버그** (producer/consumer 양쪽을 동시에 봐야 이해되는 실패)
- 통합 테스트 실패 (DB 트랜잭션, 동시성, race condition)
- E2E 테스트 (Playwright 등) flake 원인 추적

### 실전 팁
- **기본값 Haiku, fallback Sonnet**: `.failed` 시그널이 뜨면 MAX_RETRIES 재시도는 자동 Sonnet 으로 전환되도록 프롬프트에 조건부 지시
- Haiku 가 테스트 파일을 수정하려 들면 경고 — 보통 "구현을 고쳐야 하는데 테스트를 바꾸려는" 실수의 징후

### 체크리스트
- [ ] Haiku 기본
- [ ] 재시도 2회 이상 실패 시 Sonnet 수동 승격
- [ ] 통합·E2E 테스트는 초기부터 Sonnet 고려

---

## 4. 리팩토링 — `dev-refactor`

### 무엇을 하는가
테스트 green 상태 유지하면서 중복 제거·명명 개선·추출·단순화·주석 정리.

### 권장: **Sonnet**

**근거**:
- 리팩토링의 핵심 기술은 **"언제 멈출지 아는 것"**. 이것이 모델 선택을 좌우함.
- Opus: 과도하게 건드리는 경향 (over-engineering)
- Haiku: 기회를 놓치거나, 리팩토링 후 테스트 깨뜨리고 수습 못함
- **Sonnet 이 "충분히 할 거 하고 멈추는" 균형이 가장 좋음**

### ⬇ Haiku 로 다운그레이드 가능한 경우

- "오로지 rename 만" 같은 순수 기계적 작업
- 주석·포매팅·import 정리만
- 리팩토링 대상 파일이 한 개이고, 수정 범위가 명확히 한정된 경우

### ❌ Opus 불필요

- 리팩토링은 이미 작동하는 코드를 다듬는 단계 — 창의적 breakthrough 가 필요한 자리가 아님
- Opus 의 판단력을 써도 결과물이 크게 안 달라짐 → ROI 낮음

### 체크리스트
- [ ] Sonnet 기본
- [ ] 단순 rename/formatting Task 만 Haiku
- [ ] Opus 는 본 단계에서 사용하지 않음

---

## 실행 우선순위 (토큰 절감 관점)

한 곳만 바꾼다면:
1. **test 단계를 Haiku 로** — 가장 큰 절감, 가장 낮은 리스크

두 곳 바꾼다면:
2. **test + (조건부) refactor 단순 작업 Haiku** — refactor 는 단순 Task 한정

세 곳 바꾼다면:
3. **build 도 Haiku 실험** — 단, dev-test 에서 재시도 급증 여부 모니터링 필수

**설계는 마지막까지 Sonnet 유지** — 여기서의 1달러 절감이 나중에 하루치 디버깅을 만들 수 있음.

---

## 상대 비용 비교 (1개 Task 의 4 phase 합산 기준)

| 전략 | Design | Build | Test | Refactor | 상대 비용 |
|---|---|---|---|---|---|
| 전부 Opus | 1.0 | 1.0 | 1.0 | 1.0 | **1.00** |
| 전부 Sonnet | 0.20 | 0.20 | 0.20 | 0.20 | **0.20** |
| **권장 mixed** | 0.20 | 0.20 | **0.07** | 0.20 | **~0.17** |
| 공격적 mixed | 0.20 | 0.07 | 0.07 | 0.07 | **~0.10** |

→ **권장 전략으로 Opus 올인 대비 약 83% 절감**, Sonnet 올인 대비 ~15% 추가 절감.

> 주의: "공격적 mixed" 는 test 재시도 누적 리스크가 있어 실제 결과는 저 위 수치보다 나빠질 수 있음. 기본은 권장 전략.

---

## 모델 지정 방법

### CLI 직접 지정

```bash
# 새 세션 시작 시
claude --model sonnet

# 현재 세션 내 전환
/model sonnet
```

### dev-team 래퍼 스크립트에서

`.claude/worktrees/{WP-ID}-run.sh` 생성 시 WP 리더/팀원별로 별도 모델 지정:

```bash
# WP Leader — 오케스트레이션 + 스케줄링이므로 Sonnet
tmux new-window -t "$SESSION" -n "$WP_ID" \
  claude --dangerously-skip-permissions --model sonnet \
         "$(cat ${WP_ID}-prompt.txt)"

# 팀원 pane — 개발 중심이므로 Sonnet 기본
tmux split-window -t "$SESSION:$WP_ID" \
  claude --dangerously-skip-permissions --model sonnet
```

### DDTR 프롬프트에서 phase 별 서브에이전트 모델 지정

각 Phase 서브에이전트를 Agent 도구로 실행할 때 `model` 파라미터 오버라이드:

```
Agent({
  description: "dev-test 실행",
  subagent_type: "general-purpose",
  model: "haiku",    // ← phase 별 모델 스위칭
  prompt: "/dev-test TSK-01-XX ..."
})
```

### 세션 전체 환경변수로 기본값 변경

```bash
export CLAUDE_CODE_MODEL=sonnet
claude  # 이후 모든 세션이 Sonnet 기본
```

---

## 실패 시 에스컬레이션 (자동 fallback 제안)

dev-plugin 이 향후 지원할 만한 "자동 승격" 규칙 예시:

| 상황 | 동작 |
|---|---|
| dev-test Haiku 가 2회 재시도 후에도 실패 | 3회차 자동 Sonnet 재시도 |
| dev-build Haiku 실험 중 test 재시도가 평균 2회 이상 | 다음 Task 부터 자동 Sonnet 복귀 |
| dev-design 산출물 리뷰에서 "얕은 분석" 감지 | 즉시 Opus 로 재생성 후 diff 비교 |

(이것들은 현재 수동 판단 — 자동화는 후속 enhancement 로 고려)

---

## 자주 하는 실수

1. **전부 Opus 로 안전하게 가겠다** → 비용 5~10×, 품질 차이는 미미
2. **전부 Haiku 로 최대 절감** → test 재시도·design 실수로 오히려 더 비싸짐
3. **1M context 모드 default** → 일반 개발에는 불필요한 2× 가산
4. **설계만 Haiku** → 가장 하면 안 되는 조합. 하위 단계를 전부 오염시킨다
5. **리팩토링에 Opus** → 과잉 리팩토링 유발, ROI 최악

---

## 한 줄 요약

> **설계·개발·리팩토링은 Sonnet, 테스트는 Haiku, Opus 는 예약어.**
>
> 4단계 권장 기본값: Sonnet / Sonnet / Haiku / Sonnet
