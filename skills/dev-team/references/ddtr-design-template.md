# DDTR 설계 전용 프롬프트 템플릿

각 Task에 대해 `{TEMP_DIR}/task-{TSK-ID}-design.txt`를 아래 내용으로 생성한다.

```
⚠️⚠️⚠️ 최우선 규칙: 작업이 성공하든 실패하든 반드시 아래 "완료 처리" 또는 "실패 처리"를 실행하라. 시그널 파일을 생성하지 않으면 리더가 완료를 감지할 수 없다. ⚠️⚠️⚠️

아래 Task의 **설계만** 수행하라.

## 경로 변수
- DOCS_DIR = {DOCS_DIR}
- SUBPROJECT = {SUBPROJECT}

## 시작 처리 (가장 먼저 실행)
```bash
echo 'started' > {SHARED_SIGNAL_DIR}/{TSK-ID}-design.running
```

## 하트비트
`/dev` 스킬이 실행되는 동안 2분 간격으로 하트비트를 갱신하라:
```bash
touch {SHARED_SIGNAL_DIR}/{TSK-ID}-design.running
```

## 수행 절차

**Skill 도구로 `/dev` 스킬을 실행한다:**
- skill: `dev`
- args: `{SUBPROJECT} {TSK-ID} --only design {MODEL_ARG}`

`/dev --only design` 스킬이 설계 Phase만 실행하며, `design.md`를 생성하고 WBS 상태를 `[dd]`로 변경한다.

## 완료 처리 — `/dev --only design` 정상 종료 시 반드시 실행

1. 설계 산출물 커밋:
   ```bash
   git diff --quiet HEAD && git diff --cached --quiet || { git add -A && git commit -m "design: {TSK-ID} 설계 완료" 2>/dev/null || true; }
   ```
2. 시그널 파일 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   ```bash
   HASH=$(git rev-parse --short HEAD)
   echo "설계 완료 커밋: ${HASH}" > {SHARED_SIGNAL_DIR}/{TSK-ID}-design.done.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}-design.done.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}-design.done
   rm -f {SHARED_SIGNAL_DIR}/{TSK-ID}-design.running
   ```
3. 다음 지시가 올 때까지 대기. 추가 Task를 스스로 시작하지 마라.

## 실패 처리 — 복구 불가능한 에러 시 반드시 실행

1. 가능한 범위까지 git add + commit (부분 커밋이라도 보존)
2. 실패 시그널 생성 (반드시 Bash 도구로 실행, **절대 경로 사용**):
   ```bash
   echo '에러: {에러 내용 5줄 이내}' > {SHARED_SIGNAL_DIR}/{TSK-ID}-design.failed.tmp && mv {SHARED_SIGNAL_DIR}/{TSK-ID}-design.failed.tmp {SHARED_SIGNAL_DIR}/{TSK-ID}-design.failed
   rm -f {SHARED_SIGNAL_DIR}/{TSK-ID}-design.running
   ```
3. 다음 지시가 올 때까지 대기.

⚠️ 성공이든 실패든, 반드시 -design.done 또는 -design.failed 시그널 파일을 생성하라. 시그널 없이 종료하면 리더가 무한 대기한다.
⚠️ .done/.failed 생성 직후 반드시 `-design.running`을 삭제하라 — stale `.running`은 대시보드가 태스크를 "실행 중"으로 오인하게 만든다.
⚠️ 상대 경로(../.signals/) 사용 금지 — worktree에서 의도한 위치로 해석되지 않는다.
```
