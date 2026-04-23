# DDTR 할당 프롬프트 템플릿

각 Task에 대해 `{TEMP_DIR}/task-{TSK-ID}.txt`를 아래 내용으로 생성한다.

```
⚠️⚠️⚠️ 최우선 규칙: 작업이 성공하든 실패하든 반드시 아래 "완료 처리" 또는 "실패 처리"를 실행하라. 시그널 파일을 생성하지 않으면 리더가 완료를 감지할 수 없다. ⚠️⚠️⚠️

아래 Task를 `/dev` 스킬로 개발하라.

## 경로 변수
- DOCS_DIR = {DOCS_DIR}
- SUBPROJECT = {SUBPROJECT}
  (서브프로젝트가 없으면 빈 문자열, 있으면 예: `p1.5`)

## 시작 처리 (가장 먼저 실행)
```bash
echo 'started' > {SHARED_SIGNAL_DIR}/{TSK-ID}.running
```

## 하트비트
`/dev` 스킬이 실행되는 동안 2분 간격으로 하트비트를 갱신하라:
```bash
touch {SHARED_SIGNAL_DIR}/{TSK-ID}.running
```

## 수행 절차

**Skill 도구로 `/dev` 스킬을 실행한다:**
- skill: `dev`
- args: `{SUBPROJECT} {TSK-ID} {MODEL_ARG}`

`/dev` 스킬이 내부적으로 설계→구현→테스트→리팩토링 4-Phase를 순차 실행하며, 각 Phase에서 산출물(design.md, test-report.md, refactor.md)을 자동 생성한다.

## 완료 처리 — `/dev` 스킬 정상 종료 시 반드시 실행

1. 잔여 미커밋 변경 정리:
   ```bash
   git diff --quiet HEAD && git diff --cached --quiet || { git add -A && git commit -m "feat: {TSK-ID} 잔여 변경 커밋" 2>/dev/null || true; }
   ```
2. 시그널 파일 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   ```bash
   HASH=$(git rev-parse --short HEAD)
   echo "커밋: ${HASH}" > {SHARED_SIGNAL_DIR}/{TSK-ID}.done.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}.done.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}.done
   rm -f {SHARED_SIGNAL_DIR}/{TSK-ID}.running
   ```
3. 다음 지시가 올 때까지 대기. 추가 Task를 스스로 시작하지 마라.

## 실패 처리 — 복구 불가능한 에러 시 반드시 실행

1. 가능한 범위까지 git add + commit (부분 커밋이라도 보존)
2. 실패 시그널 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   ```bash
   echo '에러: {에러 내용 5줄 이내}' > {SHARED_SIGNAL_DIR}/{TSK-ID}.failed.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}.failed.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}.failed
   rm -f {SHARED_SIGNAL_DIR}/{TSK-ID}.running
   ```
3. 다음 지시가 올 때까지 대기.

⚠️ 성공이든 실패든, 반드시 .done 또는 .failed 시그널 파일을 생성하라. 시그널 없이 종료하면 리더가 무한 대기한다.
⚠️ .done/.failed 생성 직후 반드시 `.running`을 삭제하라 — stale `.running`은 대시보드가 태스크를 "실행 중"으로 오인하게 만든다.
⚠️ 상대 경로(../.signals/) 사용 금지 — worktree에서 의도한 위치로 해석되지 않는다.
```
