---
name: dev-test
description: "WBS Task 테스트 단계. 단위 + E2E 테스트 실행, 실패 시 수정 반복. 사용법: /dev-test [SUBPROJECT] TSK-00-01"
---

# /dev-test - 테스트 실행

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

## 0. 인자 파싱

Bash 도구로 실행:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.sh dev-test $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.
호출자(예: `/dev`)로부터 `DOCS_DIR`이 이미 명시적으로 전달된 경우 해당 값을 그대로 사용한다.

## 모델 선택 및 자동 에스컬레이션

이 Phase의 **기본 모델은 Haiku** (`"haiku"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-test TSK-XX-XX`) 시 Haiku 기본 적용
- 가장 기계적인 루프(에러 파싱→수정→재실행)이므로 Haiku로 충분

**자동 에스컬레이션**: Haiku로 2회 재시도 후에도 실패하면, 3회차는 Sonnet으로 자동 승격한다.
- 재시도 1-2회: `model: "haiku"`
- 재시도 3회: `model: "sonnet"` (근본 원인 분석 필요)

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 수집

Bash 도구로 실행:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.sh {DOCS_DIR}/wbs.md {TSK-ID}
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
1. domain에 맞는 테스트 실행:
   - backend: `bundle exec rspec`
   - frontend: `npm run test`
   - sidecar: `uv run pytest`
   - fullstack: 위 전부 실행
2. 실패하는 테스트가 있으면 **경계 교차 검증** 후 코드 수정:
   - 테스트 기대값(consumer)과 실제 구현(producer)을 **동시에** 읽는다
   - 함수 시그니처, 반환 타입, 필드명 등 계약이 일치하는지 확인
   - 단순 로직 버그인지, 경계 불일치(boundary mismatch)인지 구분하여 수정
3. 다시 테스트 실행
4. 최대 3회 반복. 3회 후에도 실패하면 실패 내역을 보고
   - 실패 보고 시 pass/fail/unverified 항목으로 구분하여 기록
5. QA 체크리스트의 각 항목에 대해 pass/fail 판정을 기록

## 결과 작성
{DOCS_DIR}/tasks/{TSK-ID}/test-report.md 파일에 작성한다.
양식은 .claude/skills/dev-test/template.md를 따른다.
```

### 2-1. 재시도 에스컬레이션

서브에이전트가 테스트 실패를 보고한 경우:
- **1-2회차**: 같은 프롬프트로 Haiku 서브에이전트 재실행
- **3회차**: `model: "sonnet"`으로 승격하여 재실행 (근본 원인 분석 능력 강화)

### 3. 완료 보고
- 테스트 결과 요약을 사용자에게 출력 (WBS 상태 변경 없음)
