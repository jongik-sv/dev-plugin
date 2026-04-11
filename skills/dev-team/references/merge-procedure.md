# 결과 통합 — 머지 절차 (팀리더)

## (A) 개별 WP 조기 머지 — WP 완료 즉시 실행

다른 WP가 아직 실행 중이더라도, 완료된 WP는 즉시 머지할 수 있다.
`{SHARED_SIGNAL_DIR}/{WT_NAME}.done` 시그널 파일이 생성되면 해당 WP를 머지한다
(`{WT_NAME}` = `{WP-ID}{WINDOW_SUFFIX}`).

### 0. 산출물 검증 (머지 전 필수)

**미커밋 변경 강제 커밋** (산출물 파일 소실 방지):
```bash
UNCOMMITTED=$(git -C .claude/worktrees/${WT_NAME} status --short 2>/dev/null)
if [ -n "$UNCOMMITTED" ]; then
  git -C .claude/worktrees/${WT_NAME} add -A
  git -C .claude/worktrees/${WT_NAME} commit -m "chore: ${WT_NAME} pre-merge uncommitted changes"
fi
```

WP 내 모든 Task에 대해 아래 파일이 존재하는지 확인한다:
- `{DOCS_DIR}/tasks/{TSK-ID}/design.md` — 설계 산출물
- `{DOCS_DIR}/tasks/{TSK-ID}/test-report.md` — 테스트 결과
- `{DOCS_DIR}/tasks/{TSK-ID}/refactor.md` — 리팩토링 내역
- `{DOCS_DIR}/wbs.md` 해당 Task의 status가 `[xx]`인지 확인

누락된 산출물이 있으면 시그널 내용과 대조하여 판단:
- 시그널에 실패 내용이 있으면 → 해당 Task를 부분 완료로 기록
- 파일은 없지만 시그널은 성공이면 → WP 리더에게 재확인 요청 후 진행

### 1. tmux 창 종료

해당 WP의 tmux 창(window) 종료 (pane_id 기반):
```bash
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  tmux send-keys -t "${PANE_ID}" Escape 2>/dev/null
done
```
```bash
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  tmux send-keys -t "${PANE_ID}" '/exit' Enter 2>/dev/null
done
```
```bash
tmux kill-window -t "${SESSION}:${WT_NAME}" 2>/dev/null
```
> ⚠️ 팀리더가 직접 `pkill`이나 `taskkill`을 실행하지 마라 — 다른 세션의 claude 프로세스를 오살할 수 있다. WP 리더의 cleanup 절차(`wp-leader-cleanup.md`)가 pane별 자식 프로세스를 정리한다. 테스트 프로세스는 `run-test.py`가 프로세스 그룹 단위로 자동 정리한다.

### 2. 코드 리뷰 확인

코드 리뷰는 WP 리더가 완료 전에 `codex:review`로 수행한다 (`wp-leader-cleanup.md` 참조).
시그널 파일의 리뷰 항목을 확인한다:
- **approve** / **needs-attention(수정됨)** → merge 진행
- **스킵** (일부 Task 실패) → 시그널 내용의 실패 Task를 확인하고 사용자에게 보고 후 merge 여부 판단

### 3. 머지 실행

1. main에 미커밋 변경이 있으면 먼저 커밋
2. 머지:
```bash
git merge --no-ff dev/${WT_NAME} -m "Merge dev/${WT_NAME}: {WP 제목} ({TSK-ID 목록})"
```
3. 충돌 발생 시: 사용자에게 보고하고 수동 해결 요청. 60초 후 재확인 (최대 3회). 3회 초과 시 `git merge --abort`로 해당 WP 머지 건너뛰기
4. 워크트리 + 브랜치 정리 (머지 성공 시):
   머지가 완료된 WP는 재시작 시 다시 실행할 필요가 없으므로, 즉시 정리한다:
   ```bash
   git worktree remove --force .claude/worktrees/${WT_NAME}
   git branch -d dev/${WT_NAME}
   rm -f .claude/worktrees/${WT_NAME}-prompt.txt .claude/worktrees/${WT_NAME}-init.txt .claude/worktrees/${WT_NAME}-cleanup.txt .claude/worktrees/${WT_NAME}-run.sh
   rm -f ${TEMP_DIR}/team-manifest-${WT_NAME}.md
   ```
   머지 실패/건너뛴 WP의 워크트리는 보존한다 (재시도 대비).
5. `{DOCS_DIR}/wbs.md`에서 해당 WP의 `- progress:` 값 업데이트

---

## (B) 전체 완료 머지 — 모든 WP 완료 후 실행

모니터링에서 `ALL_TEAM_MEMBERS_DONE`을 수신하면 팀리더가 아직 머지되지 않은 WP들을 순차 머지한다:

1. 각 worktree 브랜치의 변경사항을 확인 (`git log main..dev/${WT_NAME} --oneline`)
2. main 브랜치에 순차적으로 머지 (`git merge --no-ff dev/${WT_NAME}`)
   - 머지 순서: 의존성 하위 WP부터
3. 머지 후 충돌 여부 확인
   - 충돌 발생 시: 사용자에게 보고하고 수동 해결 요청. 60초 후 재확인하여 미해결 시 다시 안내 (최대 3회). 3회 초과 시 `git merge --abort`로 해당 WP 머지를 건너뛰고 다음 WP 진행
   - 충돌 없으면: 다음 브랜치 머지 진행
4. 개별 WP 정리 (조기 머지(A)에서 이미 정리된 WP는 건너뛴다):
   각 머지 성공 WP에 대해:
   ```bash
   git worktree remove --force .claude/worktrees/${WT_NAME}
   git branch -d dev/${WT_NAME}
   rm -f .claude/worktrees/${WT_NAME}-prompt.txt .claude/worktrees/${WT_NAME}-init.txt .claude/worktrees/${WT_NAME}-cleanup.txt .claude/worktrees/${WT_NAME}-run.sh
   rm -f ${TEMP_DIR}/team-manifest-${WT_NAME}.md
   ```
   머지 실패/건너뛴 WP의 워크트리는 보존한다 (재시도 대비).
5. 공유 리소스 정리:
   모든 WP가 머지 성공한 경우:
   ```bash
   rm -rf ${SHARED_SIGNAL_DIR}
   rm -f ${TEMP_DIR}/task-*.txt
   ```
   머지 실패 WP가 있으면 시그널 디렉토리와 task 프롬프트는 보존한다 (재시도 시 필요).
6. `{DOCS_DIR}/wbs.md`에서 각 WP의 `- progress:` 값을 업데이트
7. 전체 결과 요약 보고:
   - WP별 완료 Task 수
   - 성공/실패 현황
   - 머지 결과
