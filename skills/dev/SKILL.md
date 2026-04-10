---
name: dev
description: "WBS Task 전체 개발 사이클 실행 (설계→TDD구현→테스트→리팩토링). 사용법: /dev [SUBPROJECT] TSK-00-01 또는 /dev p1 TSK-00-01 --only design"
---

# /dev - Task 개발 전체 사이클

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID + 옵션)
- 예: `TSK-00-01`, `p1 TSK-00-01`, `TSK-00-01 --only design`, `p1 TSK-00-01 --only build`

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

> 한 줄 기억: 설계는 Opus, 개발·리팩토링은 Sonnet, 테스트는 Haiku.

## 실행 절차

### 0. Task 확인 및 Phase 재개 판단

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --phase-start
```
JSON 출력에서 `start_phase`를 확인한다:

| start_phase | 시작 Phase |
|-------------|-----------|
| `design` | Phase 1 (Design) |
| `build` | Phase 2 (Build) |
| `test` | Phase 3 (Test) |
| `done` | "이미 완료된 Task입니다" 출력 후 종료 |

`options.only`가 있으면 해당 Phase만 실행 (재개 판단 무시).

Task 블록이 필요하면:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

### 1. Phase: Design (설계)
서브에이전트 실행:
- **description**: "{TSK-ID} 설계"
- **model**: `options.model` 또는 `"opus"` (기본)
- **mode**: "auto"
- **prompt**:
  ```
  ${CLAUDE_PLUGIN_ROOT}/skills/dev-design/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
  DOCS_DIR={DOCS_DIR}
  TSK_ID={TSK-ID}

  [Task 블록]
  ```

### 2. Phase: Build (TDD 구현)
서브에이전트 실행:
- **description**: "{TSK-ID} TDD 구현"
- **model**: `options.model` 또는 `"sonnet"` (기본)
- **mode**: "auto"
- **prompt**:
  ```
  ${CLAUDE_PLUGIN_ROOT}/skills/dev-build/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
  DOCS_DIR={DOCS_DIR}
  TSK_ID={TSK-ID}

  [Task 블록]
  ```

### 3. Phase: Test (테스트)
서브에이전트 실행:
- **description**: "{TSK-ID} 테스트"
- **model**: `options.model` 또는 `"haiku"` (기본)
- **mode**: "auto"
- **prompt**:
  ```
  ${CLAUDE_PLUGIN_ROOT}/skills/dev-test/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
  DOCS_DIR={DOCS_DIR}
  TSK_ID={TSK-ID}
  ```
  > Test Phase는 WBS 상태를 변경하지 않는다. 최종 상태 변경(`[xx]`)은 Refactor Phase에서 수행.

### 4. Phase: Refactor (리팩토링)
서브에이전트 실행:
- **description**: "{TSK-ID} 리팩토링"
- **model**: `options.model` 또는 `"sonnet"` (기본)
- **mode**: "auto"
- **prompt**:
  ```
  ${CLAUDE_PLUGIN_ROOT}/skills/dev-refactor/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
  DOCS_DIR={DOCS_DIR}
  TSK_ID={TSK-ID}
  ```

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
