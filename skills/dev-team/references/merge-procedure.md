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
  sleep 1
  tmux send-keys -t "${PANE_ID}" '/exit' Enter 2>/dev/null
done
sleep 3
# 자식 프로세스 트리 정리 (고아 프로세스 방지, macOS/Linux: pkill, Windows/psmux: taskkill)
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  PANE_PID=$(tmux display-message -t "$PANE_ID" -p '#{pane_pid}')
  if command -v pkill &>/dev/null; then
    pkill -TERM -P "$PANE_PID" 2>/dev/null; sleep 1; pkill -9 -P "$PANE_PID" 2>/dev/null
  else
    taskkill /PID "$PANE_PID" /T /F 2>/dev/null
  fi
done
sleep 2
tmux kill-window -t "${SESSION}:${WT_NAME}" 2>/dev/null
```

### 2. 코드 리뷰 (merge 전 품질 게이트)

Agent 도구로 서브에이전트를 실행한다 (model: `"sonnet"`, mode: "auto"):
```
dev/${WT_NAME} 브랜치의 main 대비 변경사항을 리뷰하라.
Worktree 경로: .claude/worktrees/${WT_NAME}

## 1. 변경 확인
git log main..dev/${WT_NAME} --oneline
git diff main...dev/${WT_NAME}

## 2. 리뷰 관점
- 보안 취약점, 데이터 유실 위험
- 명백한 버그, 미처리 에러
- 테스트 누락
각 이슈에 severity (Critical/High/Medium/Low) 부여

## 3. Critical/High 이슈가 있으면 즉시 수정
- worktree 내 파일은 절대 경로로 접근: .claude/worktrees/${WT_NAME}/...
- 수정 후 domain별 테스트 실행: git -C .claude/worktrees/${WT_NAME} ... (출력 2>&1 | tail -200)
- 커밋: git -C .claude/worktrees/${WT_NAME} add -A && git -C .claude/worktrees/${WT_NAME} commit -m "review: {수정 요약}"

## 4. 결과 작성
{DOCS_DIR}/tasks/{WP-ID}/review.md에 작성:
- verdict: PASS | PASS_WITH_FIXES | FAIL
- 이슈 목록 (severity별)
- 수정 내역 (있으면)
```

서브에이전트 완료 후 `{DOCS_DIR}/tasks/{WP-ID}/review.md`의 verdict를 읽어 판정:
- **PASS** / **PASS_WITH_FIXES** → merge 진행
- **FAIL** → 사용자에게 보고하고 merge 중단

### 3. 머지 실행

1. main에 미커밋 변경이 있으면 먼저 커밋
2. 머지:
```bash
git merge --no-ff dev/${WT_NAME} -m "Merge dev/${WT_NAME}: {WP 제목} ({TSK-ID 목록})"
```
3. 충돌 발생 시: 사용자에게 보고하고 수동 해결 요청. 60초 후 재확인 (최대 3회). 3회 초과 시 `git merge --abort`로 해당 WP 머지 건너뛰기
4. worktree + 브랜치 정리:
```bash
git worktree remove --force .claude/worktrees/${WT_NAME}
git branch -d dev/${WT_NAME}
```
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
4. 모든 머지 완료 후 정리:
   - 시그널 디렉토리 정리: `rm -rf ${TEMP_DIR}/claude-signals/${PROJECT_NAME}${WINDOW_SUFFIX}`
   - 남은 worktree 정리: `git worktree remove --force .claude/worktrees/${WT_NAME} && git branch -d dev/${WT_NAME}`
5. `{DOCS_DIR}/wbs.md`에서 각 WP의 `- progress:` 값을 업데이트
6. 전체 결과 요약 보고:
   - WP별 완료 Task 수
   - 성공/실패 현황
   - 머지 결과
