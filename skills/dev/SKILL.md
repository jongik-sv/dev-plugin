---
name: dev
description: "WBS Task 전체 개발 사이클 실행 (설계→TDD구현→테스트→리팩토링). 사용법: /dev [SUBPROJECT] TSK-00-01 또는 /dev p1 TSK-00-01 --only design"
---

# /dev - Task 개발 전체 사이클 (WBS 모드)

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID + 옵션)
- 예: `TSK-00-01`, `p1 TSK-00-01`, `TSK-00-01 --only design`, `p1 TSK-00-01 --only build`

> **관련 스킬**: WBS가 없는 독립 기능 개발은 `/feat`를 사용한다. 두 스킬은 동일한 DFA와 하위 Phase 스킬(dev-design/build/test/refactor)을 공유하며, 차이점은 요구사항 원천(wbs.md vs spec.md)과 산출물/상태 저장 위치(`tasks/` vs `features/`)뿐이다.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev $ARGUMENTS
```
JSON 출력에서 추출:
- `docs_dir`: wbs/PRD/TRD/tasks 경로 루트
- `tsk_id`: Task ID
- `options.only`: 특정 단계만 실행 (design|build|test|refactor)
- `options.model`: 모델 오버라이드 (예: `opus`)

## 모델 선택

`options.model`이 비어 있으면 **Phase별 권장 모델**을 자동 적용한다:

| Phase | 기본 모델 | Agent `model` 값 |
|-------|-----------|-------------------|
| Design | Opus | `"opus"` |
| Build | Sonnet | `"sonnet"` |
| Test | Haiku | `"haiku"` |
| Refactor | Sonnet | `"sonnet"` |

`options.model`이 있으면 (예: `opus`) 전 단계 해당 모델.

**설계는 Haiku 금지** — `options.model=haiku`이면 Design Phase만 `sonnet`으로 자동 대체한다 (설계는 판단이 필요하므로 Haiku로 실행하지 않는다). 오케스트레이터(`/dev`, `/feat`)와 `dev-design` 내부에 동일 가드가 있으며, 오케스트레이터가 **먼저** 차단하여 사용자가 설계가 haiku로 실행된다고 오해하는 것을 방지한다.

대체가 발생하면 사용자에게 한 줄 알림:
```
ℹ️  설계는 Haiku로 실행하지 않습니다. Design Phase는 Sonnet으로 대체하여 진행합니다.
```

> 한 줄 기억: 설계는 Opus, 개발·리팩토링은 Sonnet, 테스트는 Haiku.

## 실행 절차

### 0. Task 확인 및 Phase 재개 판단

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --phase-start
```
JSON 출력에서 `start_phase`를 확인한다. `start_phase`는 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`의 `states[현재상태].phase_start` 필드에서 **단일 소스**로 결정된다. 실패는 상태를 전진시키지 않으므로 `/dev/SKILL.md`에서 별도 분기 로직은 필요 없다.

| 현재 status | start_phase | 시작 Phase |
|-------------|-------------|-----------|
| `[ ]` | `design` | Phase 1 (Design) — 최초 실행 또는 설계 미완료 |
| `[dd]` | `build` | Phase 2 (Build) — 설계 완료, 빌드 대기/재시도 |
| `[im]` | `test` | Phase 3 (Test) — 빌드 완료, 테스트 대기/재시도 |
| `[ts]` | `refactor` | Phase 4 (Refactor) — 테스트 통과, 리팩토링 대기 |
| `[xx]` | `done` | "이미 완료된 Task입니다" 출력 후 종료 |

> 실패는 상태를 되돌리지 않는다. 예를 들어 `[im]` 상태에서 테스트가 실패해도 state.json의 `last` 필드만 갱신되고 status는 `[im]`을 유지한다. `/dev` 재실행 시 phase_start는 여전히 `test` → 같은 Phase 자연 재개.

`options.only`가 있으면 해당 Phase만 실행 (재개 판단 무시).

### Phase 간 실패 게이트 (⚠️ 핵심 규칙)

**각 Phase 서브에이전트 완료 후, state.json의 `last` 필드를 확인하여 실패 여부를 판정한다:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --phase-start
```
반환 JSON의 `last.event` 값이 `*.fail`(예: `build.fail`, `test.fail`)이면 실패, `*.ok`이면 성공.

| Phase 완료 후 last.event | 다음 Phase 진행 여부 |
|--------------------------|---------------------|
| `design.ok` | Design 성공 → Build 진행 |
| (design 실패) | `design.fail`은 DFA 이벤트가 아니다. 인프라 예외로 처리 — 서브에이전트 출력의 에러를 그대로 사용자 보고 후 중단. |
| `build.ok` | Build 성공 → Test 진행 |
| `build.fail` | Build 실패 → **중단**, 사용자 보고 (status는 `[dd]` 유지) |
| `test.ok` | Test 통과 → Refactor 진행 |
| `test.fail` | Test 실패 → **중단**, 사용자 보고 (status는 `[im]` 유지) |
| `refactor.ok` | Refactor 성공 → 완료 |
| `refactor.fail` | Refactor 실패 → **중단** (status는 `[ts]` 유지, 테스트 regression 발생) |

**실패 시 중단 프로토콜**:
1. 서브에이전트 출력에서 실패 요약 추출
2. 사용자에게 보고: `"{TSK-ID} {Phase} 실패 — last={event}, status=[{현재상태}]. 수동 확인 필요."`
3. 이후 Phase는 실행하지 않는다 — 사용자가 원인 해결 후 `/dev {TSK-ID}` 재실행하면 자동 재개된다. status가 유지되므로 phase_start도 동일하게 유지됨.

Task 블록이 필요하면:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

### Phase 공통 호출 패턴

각 Phase는 동일한 서브에이전트 호출 형태를 사용한다. 표의 컬럼만 Phase별로 다르고, prompt 본문/mode/SOURCE 주입은 모두 동일.

**공통 prompt 템플릿** (`{SKILL}`만 치환):
```
${CLAUDE_PLUGIN_ROOT}/skills/{SKILL}/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
SOURCE=wbs
DOCS_DIR={DOCS_DIR}
TSK_ID={TSK-ID}

[Task 블록]   # design/build에만 첨부, test/refactor는 생략
```

| # | Phase | description | 기본 모델 (`options.model` 우선) | `{SKILL}` | Task 블록 첨부 | 완료 게이트 (`--phase-start` 재확인) |
|---|-------|-------------|---------------------------------|-----------|----------------|-------------------------------------|
| 1 | Design (설계) | `"{TSK-ID} 설계"` | `opus` (※ `haiku` 지정 시 `sonnet` 대체 — Haiku 금지 규칙) | `dev-design` | ✅ | `status=[ ]`이면 미완료 중단, `[dd]`이면 진행 |
| 2 | Build (TDD 구현) | `"{TSK-ID} TDD 구현"` | `sonnet` | `dev-build` | ✅ | `last.event=build.fail`이면 중단(status `[dd]` 유지), `status=[im]`이면 진행 |
| 3 | Test (테스트) | `"{TSK-ID} 테스트"` | `haiku` | `dev-test` | ❌ | `last.event=test.fail`이면 중단(status `[im]` 유지), `status=[ts]`이면 진행 |
| 4 | Refactor (리팩토링) | `"{TSK-ID} 리팩토링"` | `sonnet` | `dev-refactor` | ❌ | `status=[xx]`이면 완료 보고, `last.event=refactor.fail`이면 실패 보고(테스트 regression, status `[ts]` 유지) |

모든 Phase 공통: `mode: "auto"`. 게이트 통과 시 다음 Phase 호출, 실패 시 중단 후 사용자 보고("실패 시 중단 프로토콜" 참조).

### Phase 간 프로세스 정리

테스트 명령은 `run-test.py`로 래핑되어 완료/타임아웃/시그널 시 프로세스 그룹 전체가 자동 정리된다 (`references/test-commands.md` 참조).
별도의 고아 프로세스 정리는 불필요하다.

## --only 옵션 처리
- `--only design`: Phase 1만 실행
- `--only build`: Phase 2만 실행
- `--only test`: Phase 3만 실행
- `--only refactor`: Phase 4만 실행

## 완료 보고
각 Phase 완료 시 한 줄 요약을 출력하고, 전체 완료 시 최종 상태를 보고한다.
