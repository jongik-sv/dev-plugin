---
name: dev-refactor
description: "WBS Task 리팩토링 단계. 코드 품질 개선 후 테스트 확인. 사용법: /dev-refactor [SUBPROJECT] TSK-00-01"
---

# /dev-refactor - 코드 리팩토링

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-refactor $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.
호출자(예: `/dev`)로부터 `DOCS_DIR`이 이미 명시적으로 전달된 경우 해당 값을 그대로 사용한다.

## 모델 선택

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-refactor TSK-XX-XX`) 시 Sonnet 기본 적용
- "언제 멈출지 아는" 균형 감각이 핵심. Opus는 과도(over-engineering), Haiku는 부족. 단순 rename/formatting만 Haiku 가능

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 수집

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain을 확인한다. `{DOCS_DIR}/tasks/{TSK-ID}/design.md`에서 관련 파일 목록을 파악한다.

### 2. 리팩토링 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto"):

**프롬프트 구성**:
```
다음 Task에서 생성/수정된 코드를 리팩토링하라.

Task: {TSK-ID}
Domain: {domain}
관련 파일: [design.md에서 파악한 파일 목록]

## 리뷰 관점
1. 코드 중복 제거
2. 함수/메서드가 너무 길면 분리
3. 네이밍 개선
4. 불필요한 코드 제거

## 규칙
- 동작을 변경하지 않는다 (리팩토링만)
- 수정 후 반드시 테스트 실행하여 통과 확인
  - backend: `bundle exec rspec`
  - frontend: `npm run test`
  - sidecar: `uv run pytest`
- 테스트 실패 시 수정을 되돌린다

## 결과 작성
{DOCS_DIR}/tasks/{TSK-ID}/refactor.md 파일에 작성한다.
양식은 .claude/skills/dev-refactor/template.md를 따른다.
```

### 3. WBS 상태 업데이트
- `{DOCS_DIR}/wbs.md`에서 해당 Task의 `- status: [im]`를 `- status: [xx]`로 변경

### 4. 완료 보고
- 리팩토링 내역 요약과 Task 완료를 사용자에게 출력
