#!/usr/bin/env bash
# signal-helper.sh — 시그널 파일 원자적 생성/확인
# 목적: 서브에이전트 프롬프트에서 시그널 처리 지시를 1줄로 축약 → 토큰 절약
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: signal-helper.sh <command> <id> <signal-dir> [message]

Commands:
  start   <id> <dir>            .running 파일 생성
  done    <id> <dir> [message]  .done 파일 원자적 생성 (.running 제거)
  fail    <id> <dir> [message]  .failed 파일 원자적 생성 (.running 제거)
  check   <id> <dir>            상태 출력 (running|done|failed|none)
  wait    <id> <dir> [timeout]  .done 또는 .failed 대기 (기본 timeout: 무제한)
  heartbeat <id> <dir>          .running 파일 touch (하트비트)

Examples:
  signal-helper.sh start TSK-01-01 /tmp/claude-signals/proj
  signal-helper.sh done TSK-01-01 /tmp/claude-signals/proj "테스트: 5/5, 커밋: abc123"
  signal-helper.sh fail TSK-01-01 /tmp/claude-signals/proj "Phase: test, Error: assertion failed"
  signal-helper.sh check TSK-01-01 /tmp/claude-signals/proj
  signal-helper.sh wait TSK-01-01 /tmp/claude-signals/proj 600
  signal-helper.sh heartbeat TSK-01-01 /tmp/claude-signals/proj
EOF
  exit 1
}

[ $# -lt 3 ] && usage

CMD="$1"
ID="$2"
DIR="$3"
MSG="${4:-}"

mkdir -p "$DIR"

case "$CMD" in
  start)
    echo "started" > "${DIR}/${ID}.running"
    echo "OK:started"
    ;;

  done)
    printf '%s\n' "${MSG:-완료}" > "${DIR}/${ID}.done.tmp"
    mv "${DIR}/${ID}.done.tmp" "${DIR}/${ID}.done"
    rm -f "${DIR}/${ID}.running"
    echo "OK:done"
    ;;

  fail)
    printf '%s\n' "${MSG:-실패}" > "${DIR}/${ID}.failed.tmp"
    mv "${DIR}/${ID}.failed.tmp" "${DIR}/${ID}.failed"
    rm -f "${DIR}/${ID}.running"
    echo "OK:failed"
    ;;

  check)
    if [ -f "${DIR}/${ID}.done" ]; then
      echo "done"
      cat "${DIR}/${ID}.done"
    elif [ -f "${DIR}/${ID}.failed" ]; then
      echo "failed"
      cat "${DIR}/${ID}.failed"
    elif [ -f "${DIR}/${ID}.running" ]; then
      echo "running"
    else
      echo "none"
    fi
    ;;

  wait)
    TIMEOUT="${MSG:-0}"  # 0 = 무제한
    ELAPSED=0
    INTERVAL=5
    while [ ! -f "${DIR}/${ID}.done" ] && [ ! -f "${DIR}/${ID}.failed" ]; do
      sleep "$INTERVAL"
      ELAPSED=$((ELAPSED + INTERVAL))
      if [ $((ELAPSED % 300)) -eq 0 ]; then
        echo "waiting:${ID} (${ELAPSED}s elapsed)"
      fi
      if [ "$TIMEOUT" -gt 0 ] && [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "timeout:${ID} (${ELAPSED}s)"
        exit 1
      fi
    done
    if [ -f "${DIR}/${ID}.done" ]; then
      echo "DONE:${ID}"
      cat "${DIR}/${ID}.done"
    else
      echo "FAILED:${ID}"
      cat "${DIR}/${ID}.failed"
    fi
    ;;

  heartbeat)
    touch "${DIR}/${ID}.running"
    ;;

  *)
    usage
    ;;
esac
