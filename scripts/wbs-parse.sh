#!/usr/bin/env bash
# wbs-parse.sh — WBS 파일에서 Task/WP 정보를 추출하여 구조화된 형태로 출력
# 목적: LLM이 wbs.md 전체를 읽는 대신 이 스크립트 출력만 사용 → 토큰 절약
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: wbs-parse.sh <wbs-path> <ID> [mode]

Modes:
  (default)              Task/WP의 전체 필드를 JSON으로 출력
  --block                Task 블록 원문 그대로 출력
  --field <name>         단일 필드 값 출력
  --tasks                WP 하위 Task 목록 (JSON array)
  --tasks-pending        WP 하위 미완료 Task만 (status != [xx])
  --resumable-wps        실행 가능한 WP 목록 (미완료 Task가 있는 WP)
  --phase-start          Task의 현재 status 기반 시작 Phase 출력

Examples:
  wbs-parse.sh docs/wbs.md TSK-01-02
  wbs-parse.sh docs/wbs.md TSK-01-02 --block
  wbs-parse.sh docs/wbs.md TSK-01-02 --field domain
  wbs-parse.sh docs/wbs.md WP-01 --tasks
  wbs-parse.sh docs/wbs.md WP-01 --tasks-pending
  wbs-parse.sh docs/wbs.md - --resumable-wps
  wbs-parse.sh docs/wbs.md TSK-01-02 --phase-start
EOF
  exit 1
}

[ $# -lt 2 ] && usage

WBS_PATH="$1"; shift
ID="$1"; shift
MODE="${1:---json}"
[ "$MODE" = "--field" ] && { FIELD_NAME="${2:?--field requires a field name}"; }

[ ! -f "$WBS_PATH" ] && { echo "ERROR: file not found: $WBS_PATH" >&2; exit 1; }

# ──────────────────────────────────────────────
# Utility: Task 블록 추출 (### 또는 #### 레벨)
# ──────────────────────────────────────────────
extract_task_block() {
  local wbs="$1" tsk="$2"
  awk -v tsk="$tsk" '
    BEGIN { found=0; level=0 }
    {
      # heading 레벨 계산
      hl=0; for(i=1;i<=length($0);i++) { if(substr($0,i,1)=="#") hl++; else break }
    }
    # 타겟 TSK heading 매칭
    !found && hl>=2 && index($0, tsk ":") > 0 {
      found=1; level=hl; print; next
    }
    # 같거나 상위 레벨 heading → 종료
    found && hl>=2 && hl<=level && index($0, tsk ":") == 0 { exit }
    found { print }
  ' "$wbs"
}

# WP 블록 추출 (## 레벨)
extract_wp_block() {
  local wbs="$1" wp="$2"
  awk -v wp="$wp" '
    /^## / && index($0, wp ":") > 0 { found=1; print; next }
    found && /^## / { exit }
    found { print }
  ' "$wbs"
}

# 단일 필드 추출
get_field() {
  echo "$1" | grep -m1 "^- ${2}:" | sed "s/^- ${2}:[[:space:]]*//" || true
}

# JSON 문자열 이스케이프 (jq 없이도 안전)
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

# ──────────────────────────────────────────────
# Modes
# ──────────────────────────────────────────────
case "$MODE" in

# ── Raw block ──
--block)
  BLOCK=$(extract_task_block "$WBS_PATH" "$ID")
  [ -z "$BLOCK" ] && { echo "ERROR: ${ID} not found in ${WBS_PATH}" >&2; exit 1; }
  printf '%s\n' "$BLOCK"
  ;;

# ── Single field ──
--field)
  BLOCK=$(extract_task_block "$WBS_PATH" "$ID")
  [ -z "$BLOCK" ] && { echo "ERROR: ${ID} not found" >&2; exit 1; }
  get_field "$BLOCK" "$FIELD_NAME"
  ;;

# ── Task JSON (default) ──
--json)
  BLOCK=$(extract_task_block "$WBS_PATH" "$ID")
  [ -z "$BLOCK" ] && { echo "ERROR: ${ID} not found in ${WBS_PATH}" >&2; exit 1; }

  TITLE=$(echo "$BLOCK" | head -1 | sed 's/^#\{2,4\} [^:]*:[[:space:]]*//')
  CATEGORY=$(get_field "$BLOCK" "category")
  DOMAIN=$(get_field "$BLOCK" "domain")
  STATUS=$(get_field "$BLOCK" "status")
  PRIORITY=$(get_field "$BLOCK" "priority")
  ASSIGNEE=$(get_field "$BLOCK" "assignee")
  SCHEDULE=$(get_field "$BLOCK" "schedule")
  TAGS=$(get_field "$BLOCK" "tags")
  DEPENDS=$(get_field "$BLOCK" "depends")

  cat <<JSONEOF
{
  "tsk_id": "$(json_escape "$ID")",
  "title": "$(json_escape "$TITLE")",
  "category": "$(json_escape "$CATEGORY")",
  "domain": "$(json_escape "$DOMAIN")",
  "status": "$(json_escape "$STATUS")",
  "priority": "$(json_escape "$PRIORITY")",
  "assignee": "$(json_escape "$ASSIGNEE")",
  "schedule": "$(json_escape "$SCHEDULE")",
  "tags": "$(json_escape "$TAGS")",
  "depends": "$(json_escape "$DEPENDS")",
  "block": "$(json_escape "$BLOCK")"
}
JSONEOF
  ;;

# ── WP 하위 Task 목록 (전체) ──
--tasks)
  WP_BLOCK=$(extract_wp_block "$WBS_PATH" "$ID")
  [ -z "$WP_BLOCK" ] && { echo "ERROR: ${ID} not found in ${WBS_PATH}" >&2; exit 1; }

  echo "$WP_BLOCK" | awk '
    /^#{3,4} TSK-/ {
      if (tsk != "") printf "{\"tsk_id\":\"%s\",\"status\":\"%s\",\"depends\":\"%s\",\"domain\":\"%s\"}\n", tsk, status, depends, domain
      match($0, /TSK-[0-9]+(-[0-9]+)+/)
      tsk = substr($0, RSTART, RLENGTH)
      status=""; depends=""; domain=""
    }
    /^- status:/ { s=$0; sub(/^- status:[[:space:]]*/, "", s); status=s }
    /^- depends:/ { s=$0; sub(/^- depends:[[:space:]]*/, "", s); depends=s }
    /^- domain:/ { s=$0; sub(/^- domain:[[:space:]]*/, "", s); domain=s }
    END { if (tsk != "") printf "{\"tsk_id\":\"%s\",\"status\":\"%s\",\"depends\":\"%s\",\"domain\":\"%s\"}\n", tsk, status, depends, domain }
  ' | {
    echo "["
    first=true
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if $first; then first=false; else echo ","; fi
      printf '  %s' "$line"
    done
    echo ""
    echo "]"
  }
  ;;

# ── WP 하위 미완료 Task만 ──
--tasks-pending)
  WP_BLOCK=$(extract_wp_block "$WBS_PATH" "$ID")
  [ -z "$WP_BLOCK" ] && { echo "ERROR: ${ID} not found in ${WBS_PATH}" >&2; exit 1; }

  echo "$WP_BLOCK" | awk '
    /^#{3,4} TSK-/ {
      if (tsk != "" && status !~ /\[xx\]/) printf "{\"tsk_id\":\"%s\",\"status\":\"%s\",\"depends\":\"%s\",\"domain\":\"%s\"}\n", tsk, status, depends, domain
      match($0, /TSK-[0-9]+(-[0-9]+)+/)
      tsk = substr($0, RSTART, RLENGTH)
      status=""; depends=""; domain=""
    }
    /^- status:/ { s=$0; sub(/^- status:[[:space:]]*/, "", s); status=s }
    /^- depends:/ { s=$0; sub(/^- depends:[[:space:]]*/, "", s); depends=s }
    /^- domain:/ { s=$0; sub(/^- domain:[[:space:]]*/, "", s); domain=s }
    END { if (tsk != "" && status !~ /\[xx\]/) printf "{\"tsk_id\":\"%s\",\"status\":\"%s\",\"depends\":\"%s\",\"domain\":\"%s\"}\n", tsk, status, depends, domain }
  ' | {
    echo "["
    first=true
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if $first; then first=false; else echo ","; fi
      printf '  %s' "$line"
    done
    echo ""
    echo "]"
  }
  ;;

# ── 실행 가능 WP 목록 ──
--resumable-wps)
  awk '
    /^## WP-/ {
      if (wp != "" && pending > 0) printf "{\"wp_id\":\"%s\",\"pending\":%d,\"total\":%d}\n", wp, pending, total
      match($0, /WP-[0-9]+/)
      wp = substr($0, RSTART, RLENGTH)
      pending=0; total=0; in_task=0
    }
    /^#{3,4} TSK-/ { in_task=1; total++ }
    in_task && /^- status:/ {
      if ($0 !~ /\[xx\]/) pending++
      in_task=0
    }
    END { if (wp != "" && pending > 0) printf "{\"wp_id\":\"%s\",\"pending\":%d,\"total\":%d}\n", wp, pending, total }
  ' "$WBS_PATH" | {
    echo "["
    first=true
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if $first; then first=false; else echo ","; fi
      printf '  %s' "$line"
    done
    echo ""
    echo "]"
  }
  ;;

# ── Phase 시작점 판정 ──
--phase-start)
  BLOCK=$(extract_task_block "$WBS_PATH" "$ID")
  [ -z "$BLOCK" ] && { echo "ERROR: ${ID} not found" >&2; exit 1; }

  STATUS=$(get_field "$BLOCK" "status")
  DOMAIN=$(get_field "$BLOCK" "domain")

  # docs_dir는 wbs-path에서 추론 (docs/wbs.md → docs, docs/p1/wbs.md → docs/p1)
  DOCS_DIR=$(dirname "$WBS_PATH")

  case "$STATUS" in
    *"[xx]"*) PHASE="done" ;;
    *"[im]"*) PHASE="test" ;;
    *"[dd]"*)
      # design.md 존재 확인
      if [ -f "${DOCS_DIR}/tasks/${ID}/design.md" ]; then
        PHASE="build"
      else
        PHASE="design"
      fi
      ;;
    *) PHASE="design" ;;
  esac

  cat <<JSONEOF
{"tsk_id":"$ID","status":"$(json_escape "$STATUS")","domain":"$(json_escape "$DOMAIN")","start_phase":"$PHASE","docs_dir":"$(json_escape "$DOCS_DIR")"}
JSONEOF
  ;;

*)
  usage
  ;;
esac
