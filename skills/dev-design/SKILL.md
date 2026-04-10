---
name: dev-design
description: "WBS Task 설계 단계. wbs.md에서 Task를 읽고 구현 설계 후 design.md 생성. 사용법: /dev-design [SUBPROJECT] TSK-00-01"
---

# /dev-design - Task 설계

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 `TSK_ID`가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-design $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택

이 Phase의 **기본 모델은 Opus** (`"opus"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-design TSK-XX-XX`) 시 Opus 기본 적용
- 설계는 판단이 필요하므로 **Haiku 금지** (우선순위: Haiku 금지 > 호출자 오버라이드. 호출자가 `haiku`를 지정해도 Sonnet으로 대체)

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task 정보 추출

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 status, category, domain 등을 확인한다.
- status가 `[ ]`이 아니면 이미 진행 중인 Task이므로 사용자에게 확인 후 진행

Task 블록 원문이 필요하면:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

### 2. 설계 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"opus"`, mode: "auto"):

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

domain별 설계 가이드:
프로젝트의 설계 가이드를 먼저 로드한다:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
```
JSON 출력의 `design_guidance[{domain}]`에 해당 domain의 아키텍처 가이드가 있으면 그에 따라 설계한다. 없으면 프로젝트의 기존 코드 패턴을 분석하여 적절한 구조를 판단한다.

결과를 {DOCS_DIR}/tasks/{TSK-ID}/design.md 파일로 작성하라.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-design/template.md를 따른다.
```

### 3. WBS 상태 업데이트
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-update-status.py {DOCS_DIR}/wbs.md {TSK-ID} dd
```
에러 시 사용자에게 보고 후 종료.

### 4. 완료 보고
- 생성된 design.md 경로와 설계 요약을 사용자에게 출력
