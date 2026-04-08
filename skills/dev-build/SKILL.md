---
name: dev-build
description: "WBS Task TDD 구현 단계. 테스트 먼저 작성 후 구현하여 통과시킨다. 사용법: /dev-build [SUBPROJECT] TSK-00-01"
---

# /dev-build - TDD 구현

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

## 0. 인자 파싱 — 서브프로젝트 감지 (공통 규칙)

`$ARGUMENTS`를 공백으로 토큰화한 뒤 첫 번째 토큰을 검사한다:

1. `^(WP|TSK)-` 패턴이거나 `--`로 시작 → 서브프로젝트 없음, `DOCS_DIR=docs`
2. 그 외 문자열 → 서브프로젝트 이름 후보
   - `docs/{토큰}/` 존재 → `SUBPROJECT={토큰}`, `DOCS_DIR=docs/{토큰}`, `$ARGUMENTS`에서 제거
   - 존재하지 않음 → 에러 보고 후 종료

호출자(예: `/dev`)로부터 `DOCS_DIR`이 이미 명시적으로 전달된 경우 해당 값을 그대로 사용한다.

## 실행 절차

### 1. Task 정보 수집
- `{DOCS_DIR}/wbs.md`에서 `### {TSK-ID}:` 헤딩을 찾아 Task 블록 읽기
- `{DOCS_DIR}/tasks/{TSK-ID}/design.md` 읽기 (없으면 wbs.md 정보만으로 진행)
- category, domain, acceptance criteria, tech-spec 추출

### 2. TDD 구현 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (mode: "auto"):

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
