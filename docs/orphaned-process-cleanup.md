# tmux kill-window 후 자식 프로세스 잔존 이슈

> 날짜: 2026-04-09
> 발생 위치: WP-04/06/08 머지 후 tmux 창 종료 시
> 심각도: 높음 — 시스템 부하 누적, 수동 정리 필요

## 증상

머지 완료 후 tmux 창을 `kill-window`로 종료해도 Claude가 실행한 자식 프로세스
(vitest, tsc 등)가 고아 프로세스로 남아 CPU를 계속 소비.
20+ vitest 프로세스가 누적되어 시스템 전체 부하 유발.

## 원인

```
tmux kill-window
  → SIGHUP → Claude(node) 종료
  → 하지만 Claude가 spawn한 자식 프로세스(vitest 등)는
    별도 프로세스 그룹이라 SIGHUP을 받지 못함
  → 고아 프로세스로 잔존
```

## 해결 방안

### 1. 팀리더 머지 절차에서 프로세스 트리 전체 종료 (권장)

현재 `kill-window` 전에 `/exit`만 보내고 있는데, 이것만으로는 자식 프로세스가 정리되지 않는다.
pane별 프로세스 트리를 먼저 종료한 뒤 창을 닫아야 한다:

```bash
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  # 1. Claude에게 /exit 전송
  tmux send-keys -t "${PANE_ID}" Escape 2>/dev/null
  sleep 1
  tmux send-keys -t "${PANE_ID}" '/exit' Enter 2>/dev/null
done
sleep 3

# 2. 각 pane의 자식 프로세스 트리 전체 종료
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  PANE_PID=$(tmux display-message -t "$PANE_ID" -p '#{pane_pid}')
  pkill -TERM -P "$PANE_PID" 2>/dev/null
  sleep 1
  pkill -9 -P "$PANE_PID" 2>/dev/null
done
sleep 2

# 3. 창 종료
tmux kill-window -t "${SESSION}:${WT_NAME}" 2>/dev/null
```

**적용 위치**: `dev-team` 스킬의 5단계(A) "조기 머지" 절차 — `kill-window` 직전에 삽입.

### 2. WP 리더 프롬프트의 "최종 정리" 절차 강화

`references/wp-leader-prompt.md`의 "Worker 종료" 섹션에서, `/exit` 전송 후
각 pane의 자식 프로세스를 먼저 종료하도록 추가:

```bash
for pane in "${PANE_IDS[@]:1}"; do
  # 자식 프로세스 정리
  PANE_PID=$(tmux display-message -t "$pane" -p '#{pane_pid}')
  pkill -TERM -P "$PANE_PID" 2>/dev/null
  sleep 1
  # Claude 종료
  tmux send-keys -t "$pane" Escape 2>/dev/null; sleep 1
  tmux send-keys -t "$pane" '/exit' Enter 2>/dev/null
done
sleep 5
```

### 3. 머지 후 잔존 프로세스 정기 정리 스크립트

머지 완료 후 실행하여 고아 프로세스를 탐색·제거:

```bash
#!/bin/bash
# cleanup-orphaned.sh — 활성 worktree에 속하지 않는 vitest/tsc 프로세스 제거
ACTIVE_WORKTREES=$(git worktree list | awk '{print $1}')

ps aux | grep -E 'vitest|tsc' | grep -v grep | awk '{print $2}' | while read pid; do
  CWD=$(lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}')
  IS_ACTIVE=false
  for wt in $ACTIVE_WORKTREES; do
    if echo "$CWD" | grep -q "$wt"; then
      IS_ACTIVE=true; break
    fi
  done
  if [ "$IS_ACTIVE" = false ]; then
    echo "Killing orphaned PID=$pid CWD=$CWD"
    kill -9 "$pid" 2>/dev/null
  fi
done
```

## 우선순위

- **즉시 적용**: 방안 1 — 팀리더 머지 절차 수정 (dev-team 스킬)
- **즉시 적용**: 방안 2 — WP 리더 프롬프트 수정
- **보조**: 방안 3 — 정리 스크립트를 `scripts/`에 추가하여 수동/자동 실행
