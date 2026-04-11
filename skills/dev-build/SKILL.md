---
name: dev-build
description: "Task/Feature TDD 구현 단계. 테스트 먼저 작성 후 구현하여 통과시킨다. 사용법: /dev-build [SUBPROJECT] TSK-00-01"
---

# /dev-build - TDD 구현

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 (`TSK_ID` 또는 `FEAT_DIR`)가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.
>
> **SOURCE 분기**: 호출자가 `SOURCE=feat` + `FEAT_DIR` + `FEAT_NAME`을 전달하면 feat 모드, 아니면 wbs 모드. 기본값은 wbs.
>
> **⚠️ Feature 모드 진입은 `/feat`를 거쳐야 한다.** `/feat`가 `feat-init.py`로 feat_dir을 생성/확인한 뒤 FEAT_DIR을 전달한다. phase 스킬 직접 호출 시 `SOURCE=feat`를 손으로 지정하지 말 것.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-build $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 **해당 모델을 그대로 사용** (설계 Phase와 달리 Haiku 대체 없음)
- 직접 실행(`/dev-build TSK-XX-XX`) 시 Sonnet 기본 적용
- 가장 긴 단계이므로 토큰 절감 효과가 큼. **Haiku 허용**: 단순 CRUD/보일러플레이트에 한정 권장. 복잡한 비즈니스 로직은 Sonnet 유지 또는 Opus 고려

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task/Feature 정보 수집 (source 분기)

#### (A) SOURCE=wbs (기본)
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain, category 등을 확인한다. `ARTIFACT_DIR={DOCS_DIR}/tasks/{TSK-ID}`, 요구사항 원천은 Task 블록.

Task 블록 원문:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

#### (B) SOURCE=feat
Feature 상태 확인:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --status
```
`ARTIFACT_DIR={FEAT_DIR}`, 요구사항 원천은 `{FEAT_DIR}/spec.md`. domain은 spec.md의 `## 도메인` 섹션에서 추출하거나 design.md에서 확인한다.

### 1-1. design.md 필수 확인 (공통)

`{ARTIFACT_DIR}/design.md`가 없으면 **즉시 중단**하고 상태 전이 없이 사용자에게 설계 선행을 안내한다 (`/dev-design {TSK-ID}` 또는 `/feat {FEAT_NAME} --only design`). design.md는 TDD 구현의 필수 입력이다. 있으면 Read 도구로 읽는다.

### 2. TDD 구현 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto").

**프롬프트**: `${CLAUDE_PLUGIN_ROOT}/skills/dev-build/references/tdd-prompt-template.md`를 Read로 읽고 다음 변수를 치환한 본문을 전달한다.
- `{REQUIREMENT_SOURCE}`: WBS 모드는 위에서 확인한 Task 블록, Feature 모드는 `{FEAT_DIR}/spec.md` 전문
- `{DESIGN_CONTENT}`: `{ARTIFACT_DIR}/design.md` 전문
- `{SOURCE}`, `{DOCS_DIR}`, `{FEAT_DIR}`: 호출자에서 전달받은 값 그대로

### 3. 상태 전이

서브에이전트의 결과 보고(PASS / FAIL)에 따라 전이 이벤트를 결정한다:
- 모든 단위 테스트 통과 + 구현 완료 → `build.ok`
- 테스트 미통과 또는 가드레일로 중단 → `build.fail`

**(A) SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} build.ok
# 실패 시: build.fail
```

**(B) SOURCE=feat**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} build.ok
# 실패 시: build.fail
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다.

전이 스크립트 에러(파일 없음, 무효 전이) 시 사용자에게 보고 후 종료.

### 4. 완료 보고
- 성공: 생성/수정된 파일 목록과 테스트 결과 요약 출력. state.json의 `status=[im]`, `last.event=build.ok`.
- 실패: 실패 원인과 `last.event=build.fail`을 보고. status는 `[dd]` 유지 (빌드 미완료). 호출자(`/dev`, `/feat`)는 `last.event`로 실패를 감지하여 다음 Phase로 진행하지 않는다.
