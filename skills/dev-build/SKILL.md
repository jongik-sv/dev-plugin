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

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다. CLAUDE.md의 **"Build/Refactor always Sonnet"** 원칙을 따르며, 허용 모델은 **Sonnet 또는 Opus** 두 가지뿐이다. **Haiku는 금지** — Build는 실제 코드를 작성·수정하는 판단이 필요하므로 Haiku로 실행하지 않는다 (설계 Phase와 동일 정책).

모델 결정 규칙:
- 호출자(`/dev`, `/feat`, dev-team 등)가 `model` 파라미터를 명시하면 해당 값을 사용한다
- **Haiku가 전달되면 Sonnet으로 자동 대체**하고 사용자에게 한 줄 알림:
  ```
  ℹ️  Build는 Haiku로 실행하지 않습니다. Sonnet으로 대체하여 진행합니다.
  ```
- 직접 실행(`/dev-build TSK-XX-XX`) 시 Sonnet 기본 적용
- dev-team 에스컬레이션(Sonnet→Opus)으로 `opus`가 전달된 경우 그대로 사용한다

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 결정된 모델 값을 지정한다.

## 실행 절차

### 1. Task/Feature 정보 수집 (source 분기)

#### (A) SOURCE=wbs (기본)
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 `domain`, `category` 등을 확인한다. `{DOMAIN}`은 JSON의 `domain` 필드(값이 없거나 `null`이면 `default`로 설정)를 사용한다. `ARTIFACT_DIR={DOCS_DIR}/tasks/{TSK-ID}`, 요구사항 원천은 Task 블록.

Task 블록 원문:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

#### (B) SOURCE=feat
Feature 상태 확인:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --status
```
`ARTIFACT_DIR={FEAT_DIR}`, 요구사항 원천은 `{FEAT_DIR}/spec.md`. `{DOMAIN}`은 spec.md의 `## 도메인` 섹션에서 추출하거나 design.md에서 확인하며, 결정할 수 없으면 `default`로 설정한다.

### 1-1. design.md 필수 확인 (공통)

`{ARTIFACT_DIR}/design.md`가 없으면 **즉시 중단**하고 상태 전이 없이 사용자에게 설계 선행을 안내한다 (`/dev-design {TSK-ID}` 또는 `/feat {FEAT_NAME} --only design`). design.md는 TDD 구현의 필수 입력이다. 있으면 Read 도구로 읽는다.

### 2. TDD 구현 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 위 "모델 선택" 규칙으로 결정된 값 — Haiku 입력 시 Sonnet으로 대체, mode: "auto").

**프롬프트**: `${CLAUDE_PLUGIN_ROOT}/skills/dev-build/references/tdd-prompt-template.md`를 Read로 읽고 다음 변수를 치환한 본문을 전달한다.
- `{REQUIREMENT_SOURCE}`: WBS 모드는 위에서 확인한 Task 블록, Feature 모드는 `{FEAT_DIR}/spec.md` 전문
- `{DESIGN_CONTENT}`: `{ARTIFACT_DIR}/design.md` 전문
- `{DOMAIN}`: 단계 1에서 확정한 도메인 값 (`fullstack`/`frontend`/`backend`/`default` 등)
- `{SOURCE}`, `{DOCS_DIR}`, `{FEAT_DIR}`: 호출자에서 전달받은 값 그대로

**참조 파일 사전 검증**: 본 스킬이 서브에이전트에 전달하는 프롬프트는 `${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`를 참조한다. 이 파일은 플러그인 기본 포함물이므로 존재가 보장되지만, 레거시 설치 혹은 caching 오류로 누락된 경우를 대비해 서브에이전트 프롬프트가 `default-dev-config.md`를 fallback으로 사용하도록 안내되어 있다 (tdd-prompt-template.md의 "domain별 테스트" 섹션). 호출 스킬은 별도의 사전 체크를 수행하지 않는다.

**동작 보존의 기준선**: 본 단계에서 생성/통과시킨 단위 테스트는 design.md의 요구 동작을 고정하는 기준선이며, Refactor 단계에서 "동작 변경 없음"을 검증하는 재실행 대상이다. 따라서 단위 테스트는 커버리지뿐 아니라 **설계의 관찰 가능한 동작(반환값, 부작용, 에러 경계)을 직접 검사**해야 한다. 내부 구현 detail만 assert하면 리팩토링이 기능 변경 없이도 테스트를 깨뜨려 refactor.fail을 유발한다.

### 3. Verification Gate (build.ok 직전 필수)

성공 보고 시 상태 전이 직전에 phase 종료 verification을 실행한다. 차단 시 `build.ok` 호출하지 않는다. TDD red-green 사이클이 실제 발생했는지 동적 체크로 첨부한다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify-phase.py \
  --phase build \
  --target {ARTIFACT_DIR} \
  --check red_green:ok:steps={N} \
  > /tmp/verify-build-{ID}.json
```

`{N}`은 서브에이전트가 보고한 red→green 사이클 수(테스트 한 번 실패 후 통과시킨 횟수). 0이면 `red_green:fail:steps=0`. 종료 코드 1이면 build.ok로 진행하지 않는다.

상세 프로토콜: `${CLAUDE_PLUGIN_ROOT}/references/verification-protocol.md`.

### 4. 상태 전이

서브에이전트의 결과 보고(PASS / FAIL)에 따라 전이 이벤트를 결정한다:
- 모든 단위 테스트 통과 + 구현 완료 + verification 통과 → `build.ok`
- 테스트 미통과 또는 가드레일로 중단 또는 verification 차단 → `build.fail`

**(A) SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} build.ok \
  --verification /tmp/verify-build-{ID}.json
# 실패 시: build.fail (verification footer는 fail 사유 자체이므로 그대로 첨부 가능)
```

**(B) SOURCE=feat**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} build.ok \
  --verification /tmp/verify-build-{ID}.json
# 실패 시: build.fail
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다. verification footer는 phase_history 항목에 합성된다.

전이 스크립트 에러(파일 없음, 무효 전이) 시 사용자에게 보고 후 종료.

### 5. 완료 보고
- 성공: 생성/수정된 파일 목록과 테스트 결과 요약 출력. state.json의 `status=[im]`, `last.event=build.ok`, phase_history 최신 항목에 verification footer 합성됨.
- 실패: 실패 원인과 `last.event=build.fail`을 보고. status는 `[dd]` 유지. 호출자(`/dev`, `/feat`)는 `last.event`로 실패를 감지하여 다음 Phase로 진행하지 않는다.

### 자율 결정 기록

구현 중 비자명한 자율 결정(에러 처리 정책, 리트라이 정책, 라이브러리 선택, 모호 요구의 가정 등)은 `${CLAUDE_PLUGIN_ROOT}/scripts/decision-log.py append --target {ARTIFACT_DIR} --phase build ...`로 `decisions.md`에 적재한다.

### 아티팩트 경계 (build vs test)

Build 단계의 산출물은 `{ARTIFACT_DIR}/build-report.md`(template.md 형식)이며 **test-report.md와 독립**이다. 포함·불포함 경계:

| 항목 | build-report.md | test-report.md (dev-test 산출) |
|------|-----------------|--------------------------------|
| 단위 테스트 통과/실패 | ✅ Red→Green 결과 기록 | ✅ 통합 테스트 실행 결과 기록 |
| E2E 파일 생성 목록 | ✅ "생성/수정된 파일" 표에 포함 | (E2E 실행 결과만) |
| 커버리지 | ✅ build 시점 측정값 (Dev Config 정의 시) | ❌ 재측정하지 않음 |
| 정적 검증 (lint/typecheck) | ❌ 범위 밖 | ✅ dev-test가 실행 |

커버리지는 build가 measurement 주체이며, 최종 QA 판정은 dev-test가 test-report에서 수행한다. build의 coverage 섹션이 test template에는 없는 이유는 이 경계 때문이다.

### 특수 모드

본 스킬은 `/dev --only build` 또는 `/feat --only build` 방식의 phase 선택만 지원한다. `--dry-run`(테스트만 작성하고 실행하지 않음) 모드는 지원하지 않는다 — TDD의 Red 확인이 build의 필수 계약이다.
