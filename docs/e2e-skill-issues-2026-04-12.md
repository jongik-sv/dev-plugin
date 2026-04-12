# E2E 스킬 구조 결함 분석

**날짜**: 2026-04-12
**출처**: feat 스킬로 AdminClock 컴포넌트 개발 시 E2E 테스트 실패 사후 분석
**상태**: 수정 완료 (2026-04-12)

---

## 발견된 문제 요약

| # | 문제 | 관련 스킬/스크립트 | 심각도 |
|---|------|-------------------|--------|
| 1 | Build 에이전트가 모노레포에서 잘못된 앱 디렉토리에 코드 작성 | dev-design, dev-build | 높음 |
| 2 | Test 에이전트가 컴파일 불가 상태에서 23.5분(107 tool calls) 재시도 | dev-test | 높음 |
| 3 | run-test.py 타임아웃 시 에러 분류 힌트 없음 | scripts/run-test.py | 중간 |

---

## 문제 1: 모노레포 타겟 디렉토리 미발견

### 증상

Build 에이전트가 `apps/admin-web`에 작성해야 할 코드를 `apps/web`에 작성. 메인 에이전트가 사후 발견하여 수동 이동.

### 근본 원인

Design Phase(`design-prompt-template.md`)에 모노레포 구조를 파악하고 타겟 앱을 특정하는 절차가 없다.

대조적으로 Build Phase(`tdd-prompt-template.md:36-62`)에는 E2E Convention Discovery가 있어서 playwright.config 위치, testDir, baseURL을 사전 파악한다. 프로덕션 코드의 타겟 디렉토리에 대한 동일한 Discovery는 존재하지 않는다.

| 단계 | E2E Convention Discovery | Target Directory Discovery |
|------|-------------------------|---------------------------|
| dev-build (tdd-prompt-template.md) | 있음 (lines 36-62) | **없음** |
| dev-design (design-prompt-template.md) | N/A | **없음** |

### 관련 파일

- `skills/dev-design/references/design-prompt-template.md` — "생성/수정할 파일 목록" 산출물에 타겟 앱 발견 절차 없음
- `skills/dev-design/template.md` — "파일 계획" 테이블에 타겟 앱 루트 명시 구조 없음
- `skills/dev-build/references/tdd-prompt-template.md` — E2E Discovery는 있으나 타겟 디렉토리 Discovery 없음

### 수정 방향 ✅ 수정 완료

1. `design-prompt-template.md`에 "Step 0: 프로젝트 구조 파악" 추가
   - `package.json` workspaces 또는 `apps/` 하위 디렉토리 스캔
   - 요구사항 키워드(admin, dashboard, web 등)로 타겟 앱 특정
   - 모노레포가 아닌 경우 자동 스킵
2. `design template.md`의 "파일 계획" 앞에 "타겟 앱" 필드 추가하여 Build 에이전트가 명시적으로 확인 가능하게

---

## 문제 2: 컴파일 불가 상태에서의 재시도 낭비

### 증상

API에 26개 TypeScript 컴파일 에러(Prisma 스키마 snake_case vs 코드 camelCase 불일치)가 있어 서버가 기동 불가. Test 에이전트가 이를 모르고 3회 × (단위 테스트 + E2E 120s 타임아웃 + 수정 시도) 루프를 돌며 23.5분 소요.

### 근본 원인

`dev-test/SKILL.md`의 재시도 체계(lines 35-49)가 세 가지 실패 유형을 동일하게 취급한다:

| 실패 유형 | 재시도 가치 | 현재 처리 |
|-----------|------------|-----------|
| 테스트 로직 오류 | 높음 (수정 가능) | 재시도 ✅ |
| 간헐적 실패 (flaky) | 중간 | 재시도 ✅ |
| **컴파일 에러/서버 미기동** | **없음 (blocker)** | **동일하게 재시도 ❌** |

`dev-test/SKILL.md:155-173`의 "E2E 우회 금지" 규칙은 에이전트가 N/A로 우회하는 것을 막지만, blocker를 조기 감지하여 즉시 중단하는 메커니즘은 아니다.

또한 typecheck(정적 검증)가 단계 2.5(E2E 이후)에 배치되어 있어, 컴파일 에러를 E2E 타임아웃 이후에야 발견한다.

### 관련 파일

- `skills/dev-test/SKILL.md` lines 35-49 — 재시도 예산 체계 (2층 구조)
- `skills/dev-test/SKILL.md` lines 142-153 — E2E 실행 조건 (단위 통과 시에만)
- `skills/dev-test/SKILL.md` lines 155-173 — E2E 우회 금지 규칙
- `skills/dev-test/SKILL.md` lines 192-200 — 정적 검증 (단계 2.5, E2E 이후)
- `skills/dev-test/SKILL.md` lines 233-241 — 재시도 에스컬레이션

### 수정 방향

#### 2-A: Pre-E2E 컴파일 게이트 + 자동 복구 (우선순위 1) ✅ 수정 완료

단계 1-5(UI E2E 정합성 게이트) 이후, 단계 2(서브에이전트 스폰) 진입 전에 추가:

- `effective_domain`이 frontend/fullstack이면 Dev Config의 `quality_commands.typecheck` 실행
- 컴파일 실패 시 원인 분류: typecheck 에러 파일과 design.md 파일 계획의 교집합으로 판별
  - **Build regression** (교집합 있음): Build 서브에이전트를 컴파일 에러 컨텍스트와 함께 1회 재실행 → 재컴파일 성공 시 Test 진행
  - **Pre-existing** (교집합 없음) 또는 복구 실패: 즉시 `test.fail` + 분류 결과와 해결 방법 안내
- 자동 워크플로우에서 pre-existing 에러로 영원히 멈추는 문제 해결

#### 2-B: 서브에이전트 조기 중단 규칙 (우선순위 2) ✅ 수정 완료

서브에이전트 프롬프트(단계 2)에 추가:

```
## 조기 중단 조건 (retry 대상 아님)
다음 중 하나라도 해당하면 즉시 실패 보고하고 수정-재실행 사이클을 소비하지 마라:
- 서버/앱이 컴파일되지 않음 (TS errors, schema mismatch 등)
- webServer가 기동 불가 (exit code ≠ 0으로 즉시 종료)
- 동일한 에러로 2회 연속 타임아웃
이 경우 test-report.md에 "BLOCKER" 키워드와 구체적 에러를 기록한다.
```

#### 2-C: 재시도 에스컬레이션 blocker 분류 (우선순위 3) ✅ 수정 완료

단계 2-1(재시도 에스컬레이션)에 추가:

- 서브에이전트 실패 보고의 test-report.md에 "BLOCKER" 키워드가 있으면 재시도 건너뛰고 즉시 최종 실패
- 컴파일/환경 에러는 Sonnet으로 승격해도 해결 불가 — 사용자 개입 필요

---

## 문제 3: run-test.py 진단 컨텍스트 부족

### 증상

타임아웃 발생 시 에이전트가 받는 정보는 `[run-test] TIMEOUT: 900s 초과`와 마지막 200줄뿐. 그 출력이 컴파일 에러인지, 서버 기동 대기인지, 테스트 실행 중인지 구분할 구조화된 힌트가 없다.

### 근본 원인

`scripts/run-test.py:118-120`에서 타임아웃 시 단순 메시지만 출력:

```python
if timed_out:
    print(f"\n[run-test] TIMEOUT: {timeout_secs}s 초과 — 프로세스 그룹 종료됨")
    sys.exit(124)
```

### 관련 파일

- `scripts/run-test.py` lines 86-120 — 출력 캡처 및 타임아웃 처리

### 수정 방향 ✅ 수정 완료

타임아웃 시 캡처된 출력(tail deque)에서 에러 패턴을 검색하고 분류 힌트를 추가 출력:

```python
# 타임아웃 시 에러 분류 힌트
patterns = {
    "COMPILE_ERROR": [r"TS\d{4}:", r"SyntaxError", r"Cannot find module"],
    "SERVER_CRASH": [r"EADDRINUSE", r"exit code [1-9]", r"ECONNREFUSED"],
    "SCHEMA_MISMATCH": [r"Unknown arg", r"Invalid.*prisma", r"schema.*mismatch"],
}
# 매칭된 카테고리를 [run-test] HINT: 로 출력
```

이 힌트는 문제 2의 서브에이전트 조기 중단 규칙과 연동하여 에이전트가 blocker를 빠르게 판단할 수 있게 한다.

---

## 수정 우선순위

| 순위 | 수정 | 영향 | 난이도 | 관련 문제 |
|------|------|------|--------|-----------|
| 순위 | 수정 | 영향 | 난이도 | 관련 문제 | 상태 |
|------|------|------|--------|-----------|------|
| **1** | Pre-E2E 컴파일 게이트 + 자동 복구 | 23.5분 낭비 방지 | 중 | #2 | ✅ |
| **2** | 서브에이전트 조기 중단 규칙 | blocker 재시도 방지 | 낮 | #2 | ✅ |
| **3** | design-prompt-template 타겟 디렉토리 Discovery | 잘못된 앱 선택 방지 | 낮 | #1 | ✅ |
| **4** | run-test.py 에러 분류 힌트 | 에이전트 판단력 향상 | 낮 | #3 | ✅ |
| **5** | 재시도 에스컬레이션 blocker 분류 | blocker 승격 방지 | 낮 | #2 | ✅ |

---

## 참고: 프로젝트 고유 vs 스킬 구조 문제 구분

보고서 원본의 3가지 E2E 실패 원인(Node.js localStorage 비호환, Playwright config 오류, Prisma 스키마 불일치)은 **대상 프로젝트의 pre-existing 이슈**이며 dev-plugin 스킬의 결함이 아니다.

스킬의 결함은 **그 pre-existing 이슈를 만났을 때의 대응 방식**에 있다:
- 컴파일 불가를 조기에 감지하지 못함 (문제 2)
- 모노레포에서 타겟 앱을 잘못 선택함 (문제 1)
- 에러 분류 없이 동일한 재시도 루프를 반복함 (문제 2, 3)
