---
name: dev-refactor
description: "Task/Feature 리팩토링 단계. 코드 품질 개선 후 테스트 확인. 사용법: /dev-refactor [SUBPROJECT] TSK-00-01"
---

# /dev-refactor - 코드 리팩토링

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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-refactor $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-refactor TSK-XX-XX`) 시 Sonnet 기본 적용
- "언제 멈출지 아는" 균형 감각이 핵심. Opus는 과도(over-engineering), Haiku는 부족. 단순 rename/formatting만 Haiku 가능

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

### 2. 리팩토링 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto"):

**프롬프트 구성**:
```
다음 작업에서 생성/수정된 코드를 리팩토링하라.

대상: {TSK-ID 또는 FEAT_NAME}
Domain: {domain}
관련 파일: [{ARTIFACT_DIR}/design.md에서 파악한 파일 목록]

## 규칙
- 코드 품질 개선(중복/네이밍/긴 함수 분리/타입 안전성/성능/에러 핸들링) 관점에서 리뷰한다
- 동작을 변경하지 않는다 (리팩토링만). dev-build가 생성/통과시킨 단위 테스트가 "동작 보존의 기준선"이다
- 수정 후 반드시 단위 테스트 실행하여 통과 확인 (`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션 참조)
- 테스트 실패 시 리팩토링 변경을 **전부 되돌린다** (부분 되돌림 금지):
  - 권장: 서브에이전트 진입 시점에 `git stash push -u -m "dev-refactor {TSK-ID/FEAT_NAME}"`로 베이스라인을 찍고, 실패 시 `git checkout -- .` (변경된 파일만) 또는 `git stash pop`으로 완전 복구
  - 금지: "파일 A는 되돌리고 B는 유지" 같은 선택적 되돌림 — 리팩토링은 원자 단위로 성공/실패해야 다음 반복의 입력(Task 경계)이 깨지지 않음
  - 되돌림 후에도 테스트가 실패하면 `refactor.fail`을 발행하고 상태는 `[ts]` 유지 (단계 3 참조)

## 결과 작성
{ARTIFACT_DIR}/refactor.md 파일에 작성한다.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-refactor/template.md를 따른다.
```

### 3. 상태 전이

서브에이전트의 결과(PASS/FAIL)에 따라 전이 이벤트를 결정한다:
- 리팩토링 + 단위 테스트 통과 → `refactor.ok` → `status=[xx]` (완료)
- 리팩토링을 **전부 되돌렸는데도** 단위 테스트 실패 → `refactor.fail` → status는 `[ts]` 유지, `last.event=refactor.fail`로 기록

**케이스 분류** (서브에이전트가 refactor.md "비고" 섹션에 기록):
- **(A) 리팩토링 성공**: 변경 적용 후 테스트 통과. → `refactor.ok`
- **(B) 리팩토링 실패 → 전체 되돌림 후 통과**: 리팩토링을 취소했으므로 코드는 dev-test 통과 시점 상태. **결과적으로 동작 보존에 성공했으므로 `refactor.ok`** (비고에 "리팩토링 시도 후 rollback, 다음 반복에서 재시도 여지"로 기록). "리팩토링 없음 = 완료"가 허용되는 이유는 DDTR의 R이 "품질 개선 **시도**"이지 "반드시 변경"이 아니기 때문.
- **(C) 전체 되돌림 후에도 테스트 실패**: 기존 코드 자체에 regression 의심. → `refactor.fail`, status `[ts]` 유지. 비고에 "pre-existing regression suspected"를 명시하여 사용자 개입을 유도.

**재진입 규약**: `/dev {TSK-ID}` 재실행 시 `status=[ts]`, `last.event=refactor.fail` 상태에서는 phase_start가 `refactor`이므로 본 스킬이 다시 호출된다. 이전 시도의 부작용은 이미 되돌려져 있어야 하며 (규칙의 "전부 되돌린다" 참조), 본 스킬은 **현재 코드 상태 기준으로 처음부터 리팩토링을 재시작**한다. 이전 실패 원인은 서브에이전트 의사결정에 영향을 주지 않는다 (ref refactor.md 비고는 사용자용 기록).

**(A) SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} refactor.ok
# 실패 시: refactor.fail
```

**(B) SOURCE=feat**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} refactor.ok
# 실패 시: refactor.fail
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다.

### 4. 완료 보고
- 성공: 리팩토링 내역 요약과 작업 완료(`status=[xx]`, `last.event=refactor.ok`)를 사용자에게 출력.
- 실패: 실패 원인과 `last.event=refactor.fail`을 보고. status는 `[ts]` 유지. 사용자가 수동 개입 필요.
