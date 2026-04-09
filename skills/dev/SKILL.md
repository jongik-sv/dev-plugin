---
name: dev
description: "WBS Task 전체 개발 사이클 실행 (설계→TDD구현→테스트→리팩토링). 사용법: /dev [SUBPROJECT] TSK-00-01 또는 /dev p1 TSK-00-01 --only design"
---

# /dev - Task 개발 전체 사이클

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID + 옵션)
- 예: `TSK-00-01`, `p1 TSK-00-01`, `TSK-00-01 --only design`, `p1 TSK-00-01 --only build`

## 0. 인자 파싱 — 서브프로젝트 감지 (공통 규칙)

`$ARGUMENTS`를 공백으로 토큰화한 뒤 첫 번째 토큰을 검사한다:

1. `^(WP|TSK)-` 패턴이거나 `--`로 시작 → 서브프로젝트 없음, `DOCS_DIR=docs`
2. 그 외 문자열 → 서브프로젝트 이름 후보
   - `docs/{토큰}/` 존재 → `SUBPROJECT={토큰}`, `DOCS_DIR=docs/{토큰}`, `$ARGUMENTS`에서 제거
   - 존재하지 않음 → 에러 보고 후 종료 (`docs/{토큰}/ 디렉토리가 없습니다`)

이후 모든 경로(`wbs.md`, `PRD.md`, `TRD.md`, `tasks/...`)는 `{DOCS_DIR}` 기준.

## 인자 파싱 (서브프로젝트 제거 후)
- 첫 번째 남은 인자: TSK-ID (필수, 예: TSK-00-01)
- `--only <phase>`: 특정 단계만 실행 (design|build|test|refactor)
- `--model opus`: 전 단계 Opus 모델 사용 (명시하지 않으면 아래 기본 모델 적용)
- 옵션 없으면 4단계 전체 순차 실행

## 모델 선택 (docs/model-selection.md 기준)

`--model opus` 미지정 시 **Phase별 권장 모델**을 자동 적용한다:

| Phase | 기본 모델 | Agent `model` 값 |
|-------|-----------|-------------------|
| Design | Sonnet | `"sonnet"` |
| Build | Sonnet | `"sonnet"` |
| Test | Haiku | `"haiku"` |
| Refactor | Sonnet | `"sonnet"` |

`--model opus` 지정 시 전 단계 `"opus"`.

> 한 줄 기억: 설계·개발·리팩토링은 Sonnet, 테스트는 Haiku, Opus는 예약어.

## 실행 절차

### 0. Task 확인
- `{DOCS_DIR}/wbs.md`에서 `### {TSK-ID}:` 헤딩을 찾아 Task 블록 전체를 읽는다
- Task를 찾을 수 없으면 에러 출력 후 종료
- Task 정보(category, domain, status, 요구사항 등)를 추출한다

### 0-1. Phase 재개 판단

Task의 현재 status에 따라 시작 Phase를 결정한다:

| 현재 status | 시작 Phase | 조건 |
|-------------|-----------|------|
| `[ ]` | Phase 1 (Design) | — |
| `[dd]` | Phase 2 (Build) | `{DOCS_DIR}/tasks/{TSK-ID}/design.md` 존재 확인. 없으면 Phase 1부터 |
| `[im]` | Phase 3 (Test) | — |
| `[xx]` | 없음 | "이미 완료된 Task입니다" 출력 후 종료 |

`--only` 옵션이 있으면 해당 Phase만 실행 (기존 동작 유지, 재개 판단 무시).

### 1. Phase: Design (설계)
서브에이전트 실행:
- **description**: "{TSK-ID} 설계"
- **model**: `--model opus`이면 `"opus"`, 아니면 `"sonnet"` (기본)
- **prompt**: dev-design 스킬의 절차를 따른다. Task 블록 전체 + `DOCS_DIR={DOCS_DIR}` 정보를 포함하여 전달.
  1. `{DOCS_DIR}/PRD.md`, `{DOCS_DIR}/TRD.md`를 참조하여 구현 구조 설계
  2. `{DOCS_DIR}/tasks/{TSK-ID}/design.md` 생성 (생성/수정할 파일 목록, 주요 구조, 데이터 흐름)
  3. `{DOCS_DIR}/wbs.md`에서 status를 `[dd]`로 업데이트
- **mode**: "auto"

### 2. Phase: Build (TDD 구현)
서브에이전트 실행:
- **description**: "{TSK-ID} TDD 구현"
- **model**: `--model opus`이면 `"opus"`, 아니면 `"sonnet"` (기본)
- **prompt**: dev-build 스킬의 절차를 따른다. Task 블록 + design.md 내용 + `DOCS_DIR={DOCS_DIR}` 포함.
  1. acceptance criteria 기반 테스트 먼저 작성
  2. 테스트 통과하는 코드 구현
  3. domain별 테스트 프레임워크로 확인 (backend: RSpec, frontend: Vitest, sidecar: pytest)
  4. `{DOCS_DIR}/wbs.md`에서 status를 `[im]`으로 업데이트
- **mode**: "auto"

### 3. Phase: Test (테스트)
서브에이전트 실행:
- **description**: "{TSK-ID} 테스트"
- **model**: `--model opus`이면 `"opus"`, 아니면 `"haiku"` (기본)
- **prompt**: dev-test 스킬의 절차를 따른다. `DOCS_DIR={DOCS_DIR}` 포함.
  1. 전체 테스트 실행
  2. 실패 시 수정 → 재실행 (최대 3회)
  3. `{DOCS_DIR}/tasks/{TSK-ID}/test-report.md` 생성
- **mode**: "auto"

### 4. Phase: Refactor (리팩토링)
서브에이전트 실행:
- **description**: "{TSK-ID} 리팩토링"
- **model**: `--model opus`이면 `"opus"`, 아니면 `"sonnet"` (기본)
- **prompt**: dev-refactor 스킬의 절차를 따른다. `DOCS_DIR={DOCS_DIR}` 포함.
  1. 코드 품질 리뷰 및 개선
  2. 테스트 재실행으로 리그레션 확인
  3. `{DOCS_DIR}/tasks/{TSK-ID}/refactor.md` 생성
  4. `{DOCS_DIR}/wbs.md`에서 status를 `[xx]`로 업데이트
- **mode**: "auto"

## --only 옵션 처리
- `--only design`: Phase 1만 실행
- `--only build`: Phase 2만 실행
- `--only test`: Phase 3만 실행
- `--only refactor`: Phase 4만 실행

## 완료 보고
각 Phase 완료 시 한 줄 요약을 출력하고, 전체 완료 시 최종 상태를 보고한다.
