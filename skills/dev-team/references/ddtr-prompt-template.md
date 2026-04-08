# DDTR 할당 프롬프트 템플릿

각 Task에 대해 `{TEMP_DIR}/task-{TSK-ID}.txt`를 아래 내용으로 생성한다.

```
⚠️⚠️⚠️ 최우선 규칙: 작업이 성공하든 실패하든 반드시 아래 "완료 처리" 또는 "실패 처리"를 실행하라. 시그널 파일을 생성하지 않으면 리더가 완료를 감지할 수 없다. ⚠️⚠️⚠️

아래 Task를 개발하라. 각 단계를 서브에이전트(Agent 도구)로 실행하라.

## 경로 변수
- DOCS_DIR = {DOCS_DIR}
  (서브프로젝트가 없으면 `docs`, 있으면 `docs/{SUBPROJECT}`. 모든 wbs/PRD/TRD/tasks 경로는 이 변수 기준)

## 시작 처리 (가장 먼저 실행)
echo 'started' > {SHARED_SIGNAL_DIR}/{TSK-ID}.running

## 하트비트 (서브에이전트에게 위임)
각 Phase의 서브에이전트 프롬프트에 아래 지시를 포함하라:
> 작업 중 2분 간격으로 touch {SHARED_SIGNAL_DIR}/{TSK-ID}.running 을 Bash로 실행하라.

추가로 Phase 시작 전과 완료 후에도 직접 실행하라:
touch {SHARED_SIGNAL_DIR}/{TSK-ID}.running

## 담당 Task
{단일 Task 블록 — TSK-ID, domain, depends, 요구사항, 기술 스펙 포함}

## 수행 절차 — 각 단계를 서브에이전트로 실행

1. **설계 (서브에이전트)**:
   Agent 도구로 실행 (mode: "auto")
   - /dev-design 스킬의 절차를 따른다. 프롬프트에 `DOCS_DIR={DOCS_DIR}` 명시
   - {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md를 참조하여 구현 설계
   - {DOCS_DIR}/tasks/{TSK-ID}/design.md 생성 (.claude/skills/dev-design/template.md 양식)
   - {DOCS_DIR}/wbs.md에서 status를 [dd]로 변경

2. **TDD 구현 (서브에이전트)**:
   Agent 도구로 실행 (mode: "auto")
   - /dev-build 스킬의 절차를 따른다. 프롬프트에 `DOCS_DIR={DOCS_DIR}` 명시
   - design.md를 참조하여 테스트 먼저 작성 → 구현 → 테스트 통과 확인
   - domain별 테스트: backend=RSpec, frontend=Vitest, sidecar=pytest
   - {DOCS_DIR}/wbs.md에서 status를 [im]로 변경

3. **테스트 (서브에이전트)**:
   Agent 도구로 실행 (mode: "auto")
   - /dev-test 스킬의 절차를 따른다. 프롬프트에 `DOCS_DIR={DOCS_DIR}` 명시
   - 전체 테스트 실행, 실패 시 경계 교차 검증(producer↔consumer 양쪽 동시 읽기) 후 수정 (최대 3회)
   - {DOCS_DIR}/tasks/{TSK-ID}/test-report.md 생성 (.claude/skills/dev-test/template.md 양식)

4. **리팩토링 (서브에이전트)**:
   Agent 도구로 실행 (mode: "auto")
   - /dev-refactor 스킬의 절차를 따른다. 프롬프트에 `DOCS_DIR={DOCS_DIR}` 명시
   - 코드 품질 개선 → 테스트 재실행
   - {DOCS_DIR}/tasks/{TSK-ID}/refactor.md 생성 (.claude/skills/dev-refactor/template.md 양식)
   - {DOCS_DIR}/wbs.md에서 status를 [xx]로 변경

## 완료 처리 — 성공 시 반드시 실행 (건너뛰기 금지)
⚠️ 위 4단계를 모두 마친 뒤 아래 3개를 **직접** 실행하라 (서브에이전트 아님):

1. git add -A && git commit -m "feat: {TSK-ID} 구현 완료"
2. 시그널 파일 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   echo '테스트: {통과수}/{전체수}\n커밋: {해시}\n특이사항: {내용}' > {SHARED_SIGNAL_DIR}/{TSK-ID}.done.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}.done.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}.done
3. 다음 지시가 올 때까지 대기. 추가 Task를 스스로 시작하지 마라.

## 실패 처리 — 복구 불가능한 에러 시 반드시 실행 (건너뛰기 금지)
⚠️ 아래 상황에서는 완료 처리 대신 이 섹션을 실행하라:
- 테스트가 3회 재시도 후에도 실패
- 서브에이전트가 반복적으로 에러 발생
- git commit이 실패하여 복구할 수 없음
- 기타 진행 불가능한 상황

1. 가능한 범위까지 git add + commit (부분 커밋이라도 보존)
2. 실패 시그널 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   echo '실패 Phase: {phase}\n에러: {에러 내용}\n마지막 성공 Phase: {phase}\n특이사항: {내용}' > {SHARED_SIGNAL_DIR}/{TSK-ID}.failed.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}.failed.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}.failed
3. 다음 지시가 올 때까지 대기.

⚠️ 성공이든 실패든, 반드시 .done 또는 .failed 시그널 파일을 생성하라. 시그널 없이 종료하면 리더가 무한 대기한다.
⚠️ 상대 경로(../.signals/) 사용 금지 — worktree에서 의도한 위치로 해석되지 않는다.
```
