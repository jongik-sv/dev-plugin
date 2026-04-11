---
name: dev-test
description: "Task/Feature 테스트 단계. 단위 + E2E 테스트 실행, 실패 시 수정 반복. 사용법: /dev-test [SUBPROJECT] TSK-00-01"
---

# /dev-test - 테스트 실행

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 (`TSK_ID` 또는 `FEAT_DIR`)가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.
>
> **SOURCE 분기**: `SOURCE=feat` + `FEAT_DIR` + `FEAT_NAME` 전달 시 feat 모드, 아니면 wbs 모드. 기본값은 wbs.
>
> **⚠️ Feature 모드 진입은 `/feat`를 거쳐야 한다.** `/feat`가 `feat-init.py`로 feat_dir을 생성/확인한 뒤 FEAT_DIR을 전달한다. phase 스킬 직접 호출 시 `SOURCE=feat`를 손으로 지정하지 말 것.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-test $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택 및 자동 에스컬레이션

이 Phase의 **기본 모델은 Haiku** (`"haiku"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-test TSK-XX-XX`) 시 Haiku 기본 적용
- 가장 기계적인 루프(에러 파싱→수정→재실행)이므로 Haiku로 충분

**자동 에스컬레이션**: Haiku로 2회 재시도 후에도 실패하면, 3회차는 Sonnet으로 자동 승격한다.

## 재시도 예산 체계 (2층 구조)

| 층위 | 단위 | 예산 | 모델 | 책임 주체 |
|------|------|------|------|-----------|
| **시도 (attempt)** | 서브에이전트 1회 호출 | 최대 **3회** | 1·2회차 `haiku`, 3회차 `sonnet` (근본 원인 분석) | 호출자(`/dev-test` 본체). 시도 사이에 이전 시도의 실패 요약만 전달하여 재스폰 |
| **수정-재실행 사이클** | 단일 시도 내부에서 "코드 수정 + 실패한 테스트만 재실행" 1회 | 시도당 **최대 1회** | 시도 모델 상속 | 서브에이전트. 1회 사이클 후 여전히 실패하면 즉시 보고 |

3회를 초과하는 재시도는 금지한다. 본문의 "수정 예산", "내부 재실행", "추가 반복"은 모두 **수정-재실행 사이클**과 동일한 의미다 (단일 테스트 유형 실패 시 시도 1→2→3 순으로 진행. 케이스 A 성공 분기 / 케이스 B는 단계 3 본문 참조).

**실제 테스트 명령 실행 횟수 ≠ 사이클 수**: 위 예산은 **수정-재실행 사이클 수**이지 `pytest`/`vitest` 같은 명령 실행 횟수가 아니다. 한 시도 안에서 사이클 1회를 소진하지 않은 채 여러 명령이 실행될 수 있다:

- **케이스 A 성공 경로**: 단위 수정 → 단위 재실행 통과 → **E2E → 정적 검증이 이어서 실행**됨. 이 연장 실행은 새 사이클을 소비하지 않지만, E2E/정적 검증에서 실패해도 **수정 예산이 이미 소진되었으므로 추가 수정 없이 실패를 보고**한다(단계 3 케이스 A 참조).
- **최악 시나리오(한 시도 내부)**: 단위(최초) → 단위(수정 후 재실행) → E2E → 정적 검증 = **최대 4개 명령** / 사이클 1회.

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task/Feature 정보 수집 (source 분기)

#### (A) SOURCE=wbs (기본)
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain을 확인한다. `ARTIFACT_DIR={DOCS_DIR}/tasks/{TSK-ID}`, `{ARTIFACT_DIR}/design.md`에서 관련 파일 목록을 파악한다.

#### (B) SOURCE=feat
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --status
```
`ARTIFACT_DIR={FEAT_DIR}`, `{ARTIFACT_DIR}/design.md`에서 domain과 파일 목록을 파악한다.

### 2. 테스트 실행 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"haiku"`, mode: "auto"):

**프롬프트 구성**:
```
다음 요구사항의 테스트를 실행하고 모두 통과시켜라.

대상: {TSK-ID 또는 FEAT_NAME}
Domain: {domain}

## QA 체크리스트
{ARTIFACT_DIR}/design.md의 "QA 체크리스트" 섹션을 읽고, 각 항목을 테스트로 검증한다.

## 절차

### 단계 1: 단위 테스트
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션을 참조하여 domain에 맞는 단위 테스트를 실행한다.

**실패 시 E2E 테스트와 정적 검증을 건너뛰고 즉시 단계 3으로 이동**한다 (실패가 확실한 상태에서 E2E는 토큰·시간 낭비이므로 먼저 단위 테스트를 고친 뒤 E2E를 실행한다).

### 단계 2: E2E 테스트 (단위 테스트 통과 시에만 실행)
**단위 테스트가 모두 통과한 경우에만** E2E 테스트를 실행한다.
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조한다. 파일/명령이 없으면 "N/A"로 기록하고 계속 진행한다.

### 테스트 출력 제한
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "출력 제한" 섹션 참조.

### 단계 2.5: 정적 검증 (단위 테스트 통과 + Dev Config에 정의된 경우만)
**단위 테스트가 모두 통과한 경우에만** 실행한다. Dev Config의 `quality_commands`에 lint, typecheck가 정의되어 있으면 실행한다. SOURCE에 따라 로드 명령이 다르다:
- SOURCE=wbs: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config`
- SOURCE=feat: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}`

JSON 출력의 `quality_commands.lint`, `quality_commands.typecheck`를 확인한다.
- 정의된 명령만 실행한다 (없는 항목은 건너뛴다)
- 경고(warning)는 기록만 한다
- 에러가 있으면 단계 3에서 테스트 실패와 함께 수정한다

### 단계 3: 실패 수정

**경계 교차 검증 원칙** (모든 케이스 공통):
- 테스트 기대값(consumer)과 실제 구현(producer)을 **동시에** 읽는다
- 함수 시그니처, 반환 타입, 필드명 등 계약이 일치하는지 확인
- 단순 로직 버그인지, 경계 불일치(boundary mismatch)인지 구분하여 수정

**케이스 A — 단위 테스트 실패로 진입**:
1. 경계 교차 검증 후 코드 수정 (**수정-재실행 사이클 1회 소진**)
2. **단위 테스트만 재실행** (E2E는 아직 미실행이므로 재실행 대상 아님)
3. 결과 분기:
   - **통과**: 단계 2(E2E) → 단계 2.5(정적 검증)를 이어서 실행. 이 연장 실행은 새 사이클을 소비하지 않지만, E2E/정적 검증에서 실패하면 **수정-재실행 사이클 예산이 이미 소진되었으므로 추가 수정 없이** 실패 내역을 보고
   - **여전히 실패**: E2E 미실행 상태로 실패 보고. "단위 실패로 E2E skip" 명시. 추가 사이클 금지

**케이스 B — 단위 통과 후 E2E 또는 정적 검증 실패로 진입**:
1. 경계 교차 검증 후 코드 수정 (**수정-재실행 사이클 1회 소진**)
2. **실패한 테스트/검증만 재실행** (단위는 이미 통과했으므로 재실행 불필요)
3. 여전히 실패 시 실패 내역을 pass/fail/unverified로 보고. 추가 사이클 금지

**수정-재실행 사이클은 서브에이전트 시도당 최대 1회**. 추가 반복하지 마라 — 재시도(시도 수)는 상위에서 관리한다.

### 단계 4: QA 체크리스트 판정
각 항목에 pass/fail을 기록한다. 단위 실패로 E2E를 건너뛴 경우 E2E 항목은 `unverified`(사유: "단위 실패로 skip")로 기록.

## 결과 작성
{ARTIFACT_DIR}/test-report.md 파일에 작성한다.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-test/template.md를 따른다.
단위 테스트와 E2E 테스트 결과를 구분하여 기록하고, QA 체크리스트 판정(pass/fail/unverified)도 포함한다.
단위 테스트 실패로 E2E를 건너뛴 경우 E2E 섹션에 "단위 실패로 skip"을 명시한다.
```

### 2-1. 재시도 에스컬레이션 (최대 3회 시도)

서브에이전트가 테스트 실패를 보고한 경우, 이전 시도의 **실패 요약(pass/fail 항목 목록)만** 새 프롬프트에 포함하여 재시도한다. 이전 시도의 전체 테스트 출력은 포함하지 않는다.

- **1-2회차**: 같은 프롬프트 + 실패 요약으로 Haiku 서브에이전트 재실행
- **3회차**: `model: "sonnet"`으로 승격 + 실패 요약 포함하여 재실행 (근본 원인 분석 능력 강화)
- **3회 후에도 실패**: 최종 실패로 보고. 추가 재시도하지 않는다.

> 토큰 절약: 재시도 프롬프트에는 이전 시도의 test-report.md 또는 pass/fail 요약만 포함한다. 전체 로그를 전달하지 마라.

### 3. 상태 전이

서브에이전트의 최종 판정(pass/fail/unverified)에 따라 전이 이벤트를 결정한다:
- 모든 QA 체크리스트 항목이 pass → `test.ok` → `status=[ts]` (Refactor 대기)
- 하나라도 fail 또는 3회 재시도 후에도 실패 → `test.fail` → status는 `[im]` 유지, `last.event=test.fail`로 기록

**(A) SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} test.ok
# 실패 시: test.fail
```

**(B) SOURCE=feat**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} test.ok
# 실패 시: test.fail
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다.

### 4. 완료 보고
- 성공: 테스트 결과 요약 출력. state.json의 `status=[ts]`, `last.event=test.ok`.
- 실패: 실패 항목과 `last.event=test.fail`을 보고. status는 `[im]` 유지. 호출자(`/dev`, `/feat`)는 `last.event`로 실패를 감지하여 Refactor로 진행하지 않는다.
