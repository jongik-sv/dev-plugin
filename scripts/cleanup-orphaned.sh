#!/bin/bash
# cleanup-orphaned.sh — 활성 worktree에 속하지 않는 vitest/tsc 프로세스 제거
# 사용법: bash scripts/cleanup-orphaned.sh [--dry-run]
# 지원: macOS, Linux, Windows(Git Bash/WSL)
# Windows 네이티브(psmux)에서는 Git Bash 또는 WSL에서 실행 필요

DRY_RUN=false
[ "$1" = "--dry-run" ] && DRY_RUN=true

# ps 명령 가용 여부 확인
if ! command -v ps &>/dev/null; then
  echo "오류: ps 명령을 찾을 수 없습니다. Git Bash 또는 WSL에서 실행하세요." >&2
  exit 1
fi

ACTIVE_WORKTREES=$(git worktree list | awk '{print $1}')

# 프로세스 작업 디렉토리 획득: Linux(/proc), macOS(lsof), Windows Git Bash(lsof 미지원 시 생략)
get_cwd() {
  local pid=$1
  if [ -d /proc ]; then
    readlink -f /proc/"$pid"/cwd 2>/dev/null
  elif command -v lsof &>/dev/null; then
    lsof -p "$pid" 2>/dev/null | awk '/cwd/{print $NF}'
  else
    echo ""
  fi
}

ps aux | grep -E 'vitest|tsc' | grep -v grep | awk '{print $2}' | while read pid; do
  CWD=$(get_cwd "$pid")
  [ -z "$CWD" ] && continue
  IS_ACTIVE=false
  for wt in $ACTIVE_WORKTREES; do
    if echo "$CWD" | grep -q "$wt"; then
      IS_ACTIVE=true; break
    fi
  done
  if [ "$IS_ACTIVE" = false ]; then
    echo "고아 프로세스 발견: PID=$pid CWD=$CWD"
    if [ "$DRY_RUN" = false ]; then
      kill -9 "$pid" 2>/dev/null && echo "  → 종료됨"
    fi
  fi
done
