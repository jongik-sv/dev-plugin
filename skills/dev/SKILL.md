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
- **prompt**: dev-design 스킬의 절차를 따른다. Task 블록 전체 + `DOCS_DIR={DOCS_DIR}` 정보를 포함하여 전달.
  1. `{DOCS_DIR}/PRD.md`, `{DOCS_DIR}/TRD.md`를 참조하여 구현 구조 설계
  2. `{DOCS_DIR}/tasks/{TSK-ID}/design.md` 생성 (생성/수정할 파일 목록, 주요 구조, 데이터 흐름)
  3. `{DOCS_DIR}/wbs.md`에서 status를 `[dd]`로 업데이트
- **mode**: "auto"

### 2. Phase: Build (TDD 구현)
서브에이전트 실행:
- **description**: "{TSK-ID} TDD 구현"
- **model**: `options.model` 또는 `"sonnet"` (기본)
- **prompt**: dev-build 스킬의 절차를 따른다. Task 블록 + design.md 내용 + `DOCS_DIR={DOCS_DIR}` 포함.
  1. design.md의 QA 체크리스트 기반 테스트 먼저 작성
  2. 테스트 통과하는 코드 구현
  3. domain별 테스트 프레임워크로 확인 (backend: RSpec, frontend: Vitest, sidecar: pytest)
  4. `{DOCS_DIR}/wbs.md`에서 status를 `[im]`으로 업데이트
- **mode**: "auto"

### 3. Phase: Test (테스트)
서브에이전트 실행:
- **description**: "{TSK-ID} 테스트"
- **model**: `options.model` 또는 `"haiku"` (기본)
- **prompt**: dev-test 스킬의 절차를 따른다. `DOCS_DIR={DOCS_DIR}` 포함.
  1. 단위 테스트 실행 (backend: `bundle exec rspec` spec/features·system 제외, frontend: `npm run test`, sidecar: `uv run pytest -m "not e2e"`, fullstack: backend → frontend → sidecar 순차 실행 (fail-fast), database / infra / docs: N/A)
  2. E2E 테스트 실행 (backend: `bundle exec rspec spec/features spec/system`, frontend: `npm run test:e2e` → stderr에 "Missing script" 포함 시에만 `npx playwright test` 시도, sidecar: `uv run pytest -m e2e`, fullstack: backend → frontend → sidecar 순차 실행 (fail-fast), database / infra / docs: N/A). 파일/명령 없으면 N/A로 기록하고 계속 진행.
  3. 실패 시 수정 → 단위+E2E 재실행 (최대 3회, 3회차는 Sonnet 자동 승격). 테스트 출력은 `tail -200`으로 제한. 재시도 시 이전 실패 요약만 전달 (전체 로그 전달 금지).
  4. `{DOCS_DIR}/tasks/{TSK-ID}/test-report.md` 생성 (단위·E2E 결과 구분하여 기록)
  > 참고: Test Phase는 WBS 상태를 변경하지 않는다. 최종 상태 변경(`[xx]`)은 Refactor Phase에서 수행.
- **mode**: "auto"

### 4. Phase: Refactor (리팩토링)
서브에이전트 실행:
- **description**: "{TSK-ID} 리팩토링"
- **model**: `options.model` 또는 `"sonnet"` (기본)
- **prompt**: dev-refactor 스킬의 절차를 따른다. `DOCS_DIR={DOCS_DIR}` 포함.
  1. 코드 품질 리뷰 및 개선
  2. 테스트 재실행으로 리그레션 확인
  3. `{DOCS_DIR}/tasks/{TSK-ID}/refactor.md` 생성
  4. `{DOCS_DIR}/wbs.md`에서 status를 `[xx]`로 업데이트
- **mode**: "auto"

### Phase 간 프로세스 정리

각 Phase 서브에이전트 완료 직후, 고아 테스트 프로세스를 정리한다:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-orphaned.py
```
서브에이전트가 실행한 vitest/tsc 등이 종료되지 않고 남아있으면 CPU를 계속 소비하므로,
Phase 전환 시마다 실행한다 (특히 Test → Refactor 전환 시 중요).
Phase 4 (Refactor) 완료 후에도 실행한다 — Refactor 내부에서도 테스트를 실행하므로 고아 프로세스가 남을 수 있다.

## --only 옵션 처리
- `--only design`: Phase 1만 실행
- `--only build`: Phase 2만 실행
- `--only test`: Phase 3만 실행
- `--only refactor`: Phase 4만 실행

## 완료 보고
각 Phase 완료 시 한 줄 요약을 출력하고, 전체 완료 시 최종 상태를 보고한다.
