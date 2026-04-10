---
name: dev-test
description: "WBS Task 테스트 단계. 단위 + E2E 테스트 실행, 실패 시 수정 반복. 사용법: /dev-test [SUBPROJECT] TSK-00-01"
---

# /dev-test - 테스트 실행

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 `TSK_ID`가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.

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
- 재시도 1-2회: `model: "haiku"`
- 재시도 3회: `model: "sonnet"` (근본 원인 분석 필요)
- 3회 초과 재시도 금지. 총 테스트 실행 예산: 최대 6회 (시도당 내부 1회 수정-재실행 포함).

**재시도 흐름도**:
```
1회차(Haiku) → [내부: 실행 → 실패 시 1회 수정-재실행] → 실패 보고
  → 2회차(Haiku) → [내부: 실행 → 실패 시 1회 수정-재실행] → 실패 보고
    → 3회차(Sonnet) → [내부: 실행 → 실패 시 1회 수정-재실행] → 최종 실패
```

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 수집

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain을 확인한다. `{DOCS_DIR}/tasks/{TSK-ID}/design.md`에서 관련 파일 목록을 파악한다.

### 2. 테스트 실행 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"haiku"`, mode: "auto"):

**프롬프트 구성**:
```
다음 Task의 테스트를 실행하고 모두 통과시켜라.

Task: {TSK-ID}
Domain: {domain}

## QA 체크리스트
{DOCS_DIR}/tasks/{TSK-ID}/design.md의 "QA 체크리스트" 섹션을 읽고, 각 항목을 테스트로 검증한다.

## 절차

### 단계 1: 단위 테스트
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션을 참조하여 domain에 맞는 단위 테스트를 실행한다.

### 단계 2: E2E 테스트
단위 테스트 결과와 무관하게 E2E 테스트도 실행한다.
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조한다. 파일/명령이 없으면 "N/A"로 기록하고 계속 진행한다.

### 테스트 출력 제한
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "출력 제한" 섹션 참조.

### 단계 3: 실패 수정
단위 또는 E2E 테스트 중 실패가 있으면 **경계 교차 검증** 후 코드 수정:
- 테스트 기대값(consumer)과 실제 구현(producer)을 **동시에** 읽는다
- 함수 시그니처, 반환 타입, 필드명 등 계약이 일치하는지 확인
- 단순 로직 버그인지, 경계 불일치(boundary mismatch)인지 구분하여 수정

수정 후 단위 + E2E 테스트를 재실행한다. **1회 수정-재실행만 시도한다.** 여전히 실패하면 실패 내역을 pass/fail/unverified 항목으로 구분하여 보고한다. 추가 반복하지 마라 — 재시도는 상위에서 관리한다.

### 단계 4: QA 체크리스트 판정
각 항목에 대해 단위 테스트/E2E 테스트 결과를 반영하여 pass/fail 판정을 기록한다.

## 결과 작성
{DOCS_DIR}/tasks/{TSK-ID}/test-report.md 파일에 작성한다.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-test/template.md를 따른다.
단위 테스트와 E2E 테스트 결과를 구분하여 기록하고, QA 체크리스트 판정(pass/fail/unverified)도 포함한다.
```

### 2-1. 재시도 에스컬레이션 (최대 3회 시도)

서브에이전트가 테스트 실패를 보고한 경우, 이전 시도의 **실패 요약(pass/fail 항목 목록)만** 새 프롬프트에 포함하여 재시도한다. 이전 시도의 전체 테스트 출력은 포함하지 않는다.

- **1-2회차**: 같은 프롬프트 + 실패 요약으로 Haiku 서브에이전트 재실행
- **3회차**: `model: "sonnet"`으로 승격 + 실패 요약 포함하여 재실행 (근본 원인 분석 능력 강화)
- **3회 후에도 실패**: 최종 실패로 보고. 추가 재시도하지 않는다.

> 토큰 절약: 재시도 프롬프트에는 이전 시도의 test-report.md 또는 pass/fail 요약만 포함한다. 전체 로그를 전달하지 마라.

### 3. 완료 보고
- 테스트 결과 요약을 사용자에게 출력 (WBS 상태 변경 없음)
