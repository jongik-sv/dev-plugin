# WP 리더 최종 정리

이 파일은 모든 Task 완료/실패/스킵 처리 후에 실행한다.

```
⚠️ **필수**: 아래 순서대로 실행하라. 대기하거나 사용자 입력을 기다리지 마라.

## Worker 종료

각 worker pane에 대해 **개별 Bash 호출**로 종료한다 (sleep 사용 금지):
```bash
tmux send-keys -t {paneId} Escape
```
```bash
tmux send-keys -t {paneId} '/exit' Enter
```
모든 worker에 `/exit`을 보낸 뒤, 프로세스 정리:
```bash
for pane in "${PANE_IDS[@]:1}"; do
  PANE_PID=$(tmux display-message -t "$pane" -p '#{pane_pid}' 2>/dev/null)
  [ -n "$PANE_PID" ] && pkill -TERM -P "$PANE_PID" 2>/dev/null
done
```

## 정리 절차

0. **초기화 시그널 정리**:
   ```bash
   rm -f {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized
   ```

1. **코드 품질 개선** (모든 Task 성공 시에만):
   `/simplify` (Claude Code 빌트인)를 호출하여 WP 내 변경 코드를 정리한다.
   일부 Task가 실패했거나 스킵된 경우 이 단계를 건너뛴다.

2. **미커밋 변경 확인 및 커밋**:
   ```bash
   git status --short
   ```
   미커밋 변경이 있으면 `git add` + `git commit`

3. **코드 리뷰** (모든 Task 성공 시에만):
   일부 Task가 실패했거나 스킵된 경우 이 단계를 건너뛴다.

   `/codex:review --base main --wait` 실행.

   verdict가 `needs-attention`이고 Critical/High severity findings가 있으면:
   Agent 도구로 서브에이전트를 실행한다 (model: `"sonnet"`, mode: "auto"):
   ```
   아래 코드 리뷰 결과의 Critical/High 이슈를 수정하라.

   [codex:review 결과 붙여넣기]

   ## 규칙
   - Critical/High severity만 수정한다. Medium/Low는 무시.
   - 수정 후 단위 테스트 실행하여 통과 확인.
   - 커밋: git add -A && git commit -m "review: {수정 요약}"
   ```
   Medium/Low만 있으면 수정 없이 진행한다.

4. **팀리더에게 완료 보고** (시그널 파일, **절대 경로 사용**):
   > 시그널 파일 이름은 `{WT_NAME}.done`

   **모든 Task 성공 시**:
   ```bash
   cat > {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp << 'EOF'
   [{WT_NAME} 완료]
   - 완료 Task: {완료된 TSK-ID 목록}
   - 테스트: {통과 수}/{전체 수}
   - 리뷰: {approve | needs-attention(수정됨) | 스킵}
   - 커밋: {최신 커밋 해시}
   - 특이사항: {있으면 기록, 없으면 "없음"}
   EOF
   mv {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.done
   ```

   **일부 Task 실패 시에도 반드시 보고** (나머지 Task가 모두 완료/실패/스킵된 상태):
   ```bash
   cat > {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp << 'EOF'
   [{WT_NAME} 부분 완료]
   - 완료 Task: {완료된 TSK-ID 목록}
   - 실패 Task: {실패한 TSK-ID 목록}
   - 스킵 Task: {의존 실패로 스킵된 TSK-ID 목록}
   - 커밋: {최신 커밋 해시}
   - 특이사항: {실패 원인 요약}
   EOF
   mv {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.done
   ```
   > ⚠️ `{SHARED_SIGNAL_DIR}`은 팀리더가 프롬프트에 포함시킨 절대 경로이다. 상대 경로(`../.signals/`) 사용 금지.
   > ⚠️ 실패 Task가 있더라도 반드시 `.done` 시그널을 생성하라. 팀리더가 무한 대기하는 것을 방지한다.

5. **리더 자신 종료**: 위 Worker 종료 완료 확인 후 종료

**⚠️ 금지사항**:
- 시그널 파일 생성 후 추가 입력을 기다리지 마라
- 모든 Task 완료 → 시그널 생성 → 팀원 종료 → 자신 종료를 **중단 없이 연속 실행**하라
```
