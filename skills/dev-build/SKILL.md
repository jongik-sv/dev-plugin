---
name: dev-build
description: "WBS Task TDD 구현 단계. 테스트 먼저 작성 후 구현하여 통과시킨다. 사용법: /dev-build [SUBPROJECT] TSK-00-01"
---

# /dev-build - TDD 구현

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 `TSK_ID`가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-build $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

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

Task 블록 원문이 필요하면:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

### 2. TDD 구현 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"sonnet"`, mode: "auto"):

**프롬프트 구성**:
```
다음 Task를 TDD 방식으로 구현하라.

[Task 블록 + design.md 내용 붙여넣기]

## TDD 순서 (반드시 준수)
1. design.md의 QA 체크리스트 기반으로 단위 테스트를 먼저 작성
2. 테스트를 실제로 실행하여 실패를 확인 (Red)
   - 작성만 하고 실행하지 않은 테스트는 Red로 인정하지 않는다
   - 컴파일 실패 자체가 Red 신호인 경우는 인정한다
   - Red가 확인되기 전까지 프로덕션 코드를 작성하지 마라
3. 테스트를 통과하는 최소한의 코드 구현 (Green)
4. 테스트를 실행하여 전부 통과 확인
5. 커버리지 확인 (Dev Config에 정의된 경우만)
   Dev Config의 `quality_commands.coverage`가 있으면 실행한다:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
   ```
   - 커버리지 명령을 실행하고 결과를 기록한다
   - design.md의 "파일 계획"에 나열된 파일이 커버되는지 확인한다
   - 미커버 파일이 있으면 추가 테스트를 작성한다
   - 커버리지 명령이 없으면 이 단계를 건너뛴다

## domain별 테스트
### 단위 테스트 — Red→Green 실행
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션 참조.

### E2E 테스트 — 코드 작성만 (실행하지 않음)
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조하여 domain에 e2e_test가 정의되어 있으면:
- design.md의 QA 체크리스트 중 통합 케이스를 E2E 테스트 코드로 작성한다
- 프로젝트의 기존 E2E 테스트 파일을 읽고 패턴(디렉토리 구조, 셀렉터 컨벤션, fixture 등)을 따른다
- E2E 테스트를 이 단계에서 실행하지 않는다 — 실행과 검증은 dev-test가 수행한다
e2e_test가 null이면 이 단계를 건너뛴다.

## 규칙
- 기존 코드의 패턴과 컨벤션을 따른다
- 불필요한 파일을 생성하지 않는다
- 모든 단위 테스트 통과가 목표이다. 가드레일에 의해 미해결 테스트가 있으면 결과를 FAIL로 보고한다
- E2E는 실행하지 않으므로 통과 기준에 포함하지 않는다

## 가드레일
- 같은 테스트가 3회 연속 같은 이유로 실패하면 해당 테스트 수정을 중단하고 나머지 구현을 계속한다 (test.skip 등 코드 변경 금지)
- 이전에 통과하던 테스트가 수정 후 실패하면 (regression) 되돌리고 다른 접근을 1회 시도한다. 재발하면 되돌리고 원인 보고
- design.md에 없는 파일이 필요하면 생성 이유를 결과 보고에 기록하고 계속 진행한다

## 결과 보고
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-build/template.md를 참고한다.
```

### 3. WBS 상태 업데이트
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-update-status.py {DOCS_DIR}/wbs.md {TSK-ID} im
```
에러 시 사용자에게 보고 후 종료.

### 4. 완료 보고
- 생성/수정된 파일 목록과 테스트 결과 요약을 사용자에게 출력
