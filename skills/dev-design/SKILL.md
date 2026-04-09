---
name: dev-design
description: "WBS Task 설계 단계. wbs.md에서 Task를 읽고 구현 설계 후 design.md 생성. 사용법: /dev-design [SUBPROJECT] TSK-00-01"
---

# /dev-design - Task 설계

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

## 0. 인자 파싱 — 서브프로젝트 감지 (공통 규칙)

`$ARGUMENTS`를 공백으로 토큰화한 뒤 첫 번째 토큰을 검사한다:

1. `^(WP|TSK)-` 패턴이거나 `--`로 시작 → 서브프로젝트 없음, `DOCS_DIR=docs`
2. 그 외 문자열 → 서브프로젝트 이름 후보
   - `docs/{토큰}/` 존재 → `SUBPROJECT={토큰}`, `DOCS_DIR=docs/{토큰}`, `$ARGUMENTS`에서 제거
   - 존재하지 않음 → 에러 보고 후 종료

호출자(예: `/dev`)로부터 `DOCS_DIR`이 이미 명시적으로 전달된 경우 해당 값을 그대로 사용한다.

## 모델 선택

이 Phase의 **기본 모델은 Sonnet** (`"sonnet"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-design TSK-XX-XX`) 시 Sonnet 기본 적용
- 설계는 판단이 필요하므로 **Haiku 금지**. 보안/동시성/분산 경계 Task는 Opus 고려

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 추출
- `{DOCS_DIR}/wbs.md`에서 `### {TSK-ID}:` 헤딩을 찾아 Task 블록 전체를 읽는다
- 추출 항목: category, domain, status, requirements, acceptance, tech-spec, api-spec, data-model, ui-spec
- status가 `[ ]`이 아니면 이미 진행 중인 Task이므로 사용자에게 확인 후 진행

### 2. 설계 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto"):

**프롬프트 구성**:
```
다음 Task를 설계하라. 코드를 작성하지 말고 설계만 한다.

[Task 블록 전체 붙여넣기]

참고 문서: {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md

산출물:
1. 생성/수정할 파일 목록과 각 파일의 역할
2. 주요 함수/클래스/컴포넌트 이름과 책임
3. 데이터 흐름 요약 (입력 → 처리 → 출력)
4. 의존성 및 선행 조건
5. QA 체크리스트 — dev-test에서 검증할 항목 (정상/엣지/에러/통합 케이스). 각 항목은 pass/fail로 판정 가능한 구체적 문장으로 작성

domain별 가이드:
- backend: Rails API 컨트롤러, 모델, 서비스 구조
- frontend: React 컴포넌트, 페이지, 스토어 구조
- sidecar: FastAPI 엔드포인트, 서비스 구조
- infrastructure: 설정 파일, 환경 구성

결과를 {DOCS_DIR}/tasks/{TSK-ID}/design.md 파일로 작성하라.
양식은 .claude/skills/dev-design/template.md를 따른다.
```

### 3. WBS 상태 업데이트
- `{DOCS_DIR}/wbs.md`에서 해당 Task의 `- status: [ ]`를 `- status: [dd]`로 변경 (Edit 도구 사용)

### 4. 완료 보고
- 생성된 design.md 경로와 설계 요약을 사용자에게 출력
