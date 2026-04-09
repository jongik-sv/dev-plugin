---
name: dev-build
description: "WBS Task TDD 구현 단계. 테스트 먼저 작성 후 구현하여 통과시킨다. 사용법: /dev-build [SUBPROJECT] TSK-00-01"
---

# /dev-build - TDD 구현

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-build $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.
호출자(예: `/dev`)로부터 `DOCS_DIR`이 이미 명시적으로 전달된 경우 해당 값을 그대로 사용한다.

## 모델 선택

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-build TSK-XX-XX`) 시 Sonnet 기본 적용
- 가장 긴 단계이므로 토큰 절감 효과가 큼. 단순 CRUD는 Haiku 실험 가능, 복잡한 비즈니스 로직은 Opus 고려

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 수집

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain, category 등을 확인한다. `{DOCS_DIR}/tasks/{TSK-ID}/design.md`를 Read 도구로 읽는다 (없으면 wbs.md 정보만으로 진행).

### 2. TDD 구현 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto"):

**프롬프트 구성**:
```
다음 Task를 TDD 방식으로 구현하라.

[Task 블록 + design.md 내용 붙여넣기]

## TDD 순서 (반드시 준수)
1. acceptance criteria 기반으로 테스트를 먼저 작성
2. 테스트가 실패하는 것을 확인 (Red)
3. 테스트를 통과하는 최소한의 코드 구현 (Green)
4. 테스트를 실행하여 전부 통과 확인

## domain별 테스트 프레임워크
- backend: RSpec (`bundle exec rspec`)
- frontend: Vitest (`npm run test`)
- sidecar: pytest (`uv run pytest`)

## 규칙
- 기존 코드의 패턴과 컨벤션을 따른다
- 불필요한 파일을 생성하지 않는다
- 테스트가 모두 통과해야 완료이다
```

### 3. WBS 상태 업데이트
- `{DOCS_DIR}/wbs.md`에서 해당 Task의 `- status: [dd]`를 `- status: [im]`로 변경

### 4. 완료 보고
- 생성/수정된 파일 목록과 테스트 결과 요약을 사용자에게 출력
