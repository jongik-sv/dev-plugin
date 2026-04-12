# codex:review / dev-refactor 역할 분석

> 작성일: 2026-04-12

코드리뷰(`codex:review`)와 리팩토링(`dev-refactor`)의 역할 경계와 남은 문제를 정리한다.

---

## 1. 역할 비교표

| | `dev-refactor` | `codex:review` |
|---|---|---|
| **유형** | 플러그인 Skill (DDTR Phase 4) | 외부 플러그인 SlashCommand |
| **목적** | 코드 품질 개선 (리팩토링) | 코드 리뷰 (결함 탐지 + Critical/High 자동 수정) |
| **스코프** | 단일 Task/Feature의 관련 파일 | branch vs main 전체 diff |
| **테스트 검증** | 필수 (실패 시 롤백) | 수정 시 테스트 실행하나 **실패 시 롤백 규칙 없음** |
| **상태 전이** | `refactor.ok/fail` → DFA | `.done` 시그널에 `REVIEW_STATUS` 기록 |
| **산출물** | `refactor.md` + 수정된 소스 | 리뷰 verdict (approve / needs-attention) |
| **실행 시점** | DDTR Phase 4 (Task별) | WP Leader cleanup (WP 전체 완료 후) |

---

## 2. 실행 순서 (dev-team)

```
각 Task: Design → Build → Test → dev-refactor (테스트 통과 확인) → [xx]
                                        ↓
WP Leader cleanup: 미커밋 확인/커밋 → codex:review → 팀리더 보고
```

---

## 3. 남은 문제

### 문제 1: `codex:review` 수정 실패 시 롤백 전략 부재

`dev-refactor`는 "테스트 실패 시 수정을 되돌린다"고 명시한다 (SKILL.md 67행). 하지만 `codex:review`의 수정 서브에이전트 프롬프트(wp-leader-cleanup.md)에는:

```
- 수정 후 단위 테스트 실행하여 통과 확인.
- 커밋: git add -A && git commit -m "review: {수정 요약}"
```

테스트 **실패 시** 어떻게 하라는 지시가 없다. 실패한 수정이 커밋에 포함되거나, 정리 안 된 수정이 남을 수 있다.

**위험도**: 높음 — `dev-refactor`가 검증한 코드를 `codex:review` 수정이 깨뜨릴 수 있다.

### 문제 2: 두 도구의 역할 경계

| 관심사 | 담당 도구 | 상태 |
|---|---|---|
| Task 내 코드 품질 개선 | dev-refactor | 명확 |
| Cross-Task 중복/패턴 리뷰 | codex:review | WP 전체 diff를 보므로 커버 가능 |
| 보안/심각도 분류 리뷰 | codex:review | 명확 (Critical/High/Medium/Low) |
| 수정 후 regression 방지 | dev-refactor만 보장 | codex:review 수정은 미보장 (문제 1) |

**역할 분담은 명확해졌다**: `dev-refactor`는 Task 단위 품질 개선(동작 보존 + 테스트 게이트), `codex:review`는 WP 전체 관점 리뷰(보안/패턴/심각도 분류). 문제 1만 해결하면 두 도구가 상호 보완적으로 동작한다.

---

## 4. 개선 방안

### 방안 A: `codex:review` 수정 서브에이전트에 롤백 규칙 추가

`wp-leader-cleanup.md`의 수정 프롬프트에 추가:

```
- 테스트 실패 시 수정을 되돌린다 (git checkout .)
- 되돌린 경우 REVIEW_STATUS에 "needs-attention(수정실패-롤백)" 기록
```

**효과**: `dev-refactor`와 동일한 안전장치. 즉시 적용 가능.

---

## 5. 최종 구조

```
┌─────────────────────────────────────────────────┐
│ DDTR Phase 4: dev-refactor                      │
│ - Task 단위 코드 품질 개선                        │
│ - 동작 변경 금지 (리팩토링만)                      │
│ - 단위 테스트 필수 → 실패 시 롤백                  │
│ - 산출물: refactor.md                            │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│ WP Leader cleanup: codex:review                 │
│ - WP 전체 diff 대상 코드 리뷰                     │
│ - Critical/High만 자동 수정                       │
│ - 수정 후 테스트 → 실패 시 롤백 (방안 A 적용 후)    │
│ - 산출물: REVIEW_STATUS in .done 시그널           │
└─────────────────────────────────────────────────┘

```
