---
name: dev-design
description: "Task/Feature 설계 단계. WBS Task 또는 독립 Feature를 읽고 구현 설계 후 design.md 생성. 사용법: /dev-design [SUBPROJECT] TSK-00-01"
---

# /dev-design - Task/Feature 설계

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 (`TSK_ID` 또는 `FEAT_DIR`)가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.
>
> **SOURCE 분기**: 호출자가 `SOURCE=feat` + `FEAT_DIR` + `FEAT_NAME`을 전달하면 feat 모드(docs/features/{name}/ 기준), 아니면 wbs 모드(docs/tasks/{TSK-ID}/ 기준)로 동작한다. 기본값은 wbs.
>
> **⚠️ Feature 모드 진입은 `/feat`를 거쳐야 한다.** `/feat`가 `feat-init.py`로 feat_dir을 생성/확인한 뒤 FEAT_DIR을 전달한다. phase 스킬 직접 호출 시 `SOURCE=feat`를 손으로 지정하지 말 것.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-design $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택

이 Phase의 **기본 모델은 호출자 지정값** → 없으면 **Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, `/feat`)가 복잡도 기반으로 결정한 `model` 파라미터를 우선 사용
- 직접 실행(`/dev-design TSK-XX-XX`) 시 Sonnet 기본 적용 (복잡한 Task라면 `--model opus` 명시)
- 설계는 판단이 필요하므로 **Haiku 금지** (호출자가 `haiku`를 지정해도 Sonnet으로 대체)

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task/Feature 정보 추출 (source 분기)

**SOURCE에 따라 요구사항 원천과 경로가 달라진다:**

#### (A) SOURCE=wbs (기본)
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 status, category, domain 등을 확인한다.
- status가 `[ ]`이 아니면 이미 진행 중인 Task이므로 사용자에게 확인 후 진행

Task 블록 원문:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

변수 치환: `ARTIFACT_DIR={DOCS_DIR}/tasks/{TSK-ID}`, `REQUIREMENT_SOURCE`=위에서 추출한 Task 블록 + PRD/TRD 참조.

#### (B) SOURCE=feat
Feature의 현재 상태 확인:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --status
```
JSON 출력에서 `state`를 확인한다.

요구사항은 `{FEAT_DIR}/spec.md`를 Read 도구로 읽어 추출한다. spec.md의 `## 도메인` 섹션이 비어 있으면 dev-design이 코드 분석을 통해 domain을 추론한다.

변수 치환: `ARTIFACT_DIR={FEAT_DIR}`, `REQUIREMENT_SOURCE`=spec.md 전체.

### 2. 설계 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto").

**프롬프트**: `${CLAUDE_PLUGIN_ROOT}/skills/dev-design/references/design-prompt-template.md`를 Read로 읽고 다음 변수를 치환한 본문을 전달한다.
- `{REQUIREMENT_SOURCE}`: WBS 모드는 위에서 추출한 Task 블록, Feature 모드는 `{FEAT_DIR}/spec.md` 전문
- `{SOURCE}`, `{DOCS_DIR}`, `{FEAT_DIR}`, `{ARTIFACT_DIR}`: 1단계에서 결정된 값 그대로

### 3. 상태 전이

서브에이전트가 design.md를 정상 생성하면 `design.ok` 이벤트를 발생시킨다. 설계 실패는 **DFA 이벤트가 아니다** — 서브에이전트 크래시/사용자 중단/I-O 에러 등 인프라 예외로 취급하며, 상태는 `[ ]`에 머문 채 그대로 사용자에게 에러를 보고하고 종료한다.

**(A) SOURCE=wbs** — Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} design.ok
```

**(B) SOURCE=feat** — Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} design.ok
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다. 스크립트는 사이드카 `state.json`을 원천으로 갱신한 뒤 wbs.md status 줄(wbs 모드)을 동기화한다.

전이 스크립트 자체가 에러(파일 없음 등)를 반환하면 사용자에게 보고 후 종료.

### 4. 완료 보고
- 성공: 생성된 design.md 경로와 설계 요약 출력. state.json의 `status`는 `[dd]`, `last.event`는 `design.ok`.
- 실패 (인프라 예외): 실패 원인을 그대로 사용자에게 보고. 상태는 `[ ]` 유지. 호출자(`/dev`, `/feat` 오케스트레이터)는 서브에이전트의 에러 출력과 미생성된 design.md로 실패를 감지한다.
