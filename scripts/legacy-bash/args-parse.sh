#!/usr/bin/env bash
# args-parse.sh — 스킬 공통 인자 파싱 (서브프로젝트 감지 + 옵션 추출)
# 목적: 7개 스킬의 동일 보일러플레이트를 하나의 스크립트로 대체 → 토큰 절약
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: args-parse.sh <skill> [arguments...]

Skills: dev, dev-design, dev-build, dev-test, dev-refactor, dev-team, wbs

Output: JSON with parsed arguments
  {
    "subproject": "",        // 서브프로젝트 이름 (없으면 빈 문자열)
    "docs_dir": "docs",     // docs 경로
    "tsk_id": "TSK-01-02",  // Task ID (해당 시)
    "wp_ids": ["WP-01"],    // WP ID 목록 (해당 시)
    "options": {             // 스킬별 옵션
      "only": "",
      "model": "",
      "team_size": 3,
      "pool_size": 5,
      "scale": "",
      "start_date": "",
      "estimate_only": false
    }
  }

Examples:
  args-parse.sh dev "p1 TSK-01-01 --only design"
  args-parse.sh dev-team "p1 WP-01 WP-02 --team-size 5 --model opus"
  args-parse.sh wbs "p1 --scale large --start-date 2026-04-01"
EOF
  exit 1
}

[ $# -lt 1 ] && usage

SKILL="$1"; shift
ARGS="${*:-}"

# ──────────────────────────────────────────────
# JSON escape
# ──────────────────────────────────────────────
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

# ──────────────────────────────────────────────
# Parse
# ──────────────────────────────────────────────
SUBPROJECT=""
DOCS_DIR="docs"
TSK_ID=""
WP_IDS=()
OPT_ONLY=""
OPT_MODEL=""
OPT_TEAM_SIZE=3
OPT_POOL_SIZE=5
OPT_SCALE=""
OPT_START_DATE=""
OPT_ESTIMATE_ONLY=false
OPT_WORKDIR=""
OPT_LEADER=false
OPT_CLAIM=false

# Tokenize
read -ra TOKENS <<< "$ARGS"
IDX=0

# ── 1단계: 서브프로젝트 감지 ──
if [ ${#TOKENS[@]} -gt 0 ]; then
  FIRST="${TOKENS[0]}"
  # --로 시작하면 옵션 → 서브프로젝트 아님
  if [[ "$FIRST" == --* ]]; then
    : # skip
  # WP- 또는 TSK- 패턴 → 서브프로젝트 아님
  elif [[ "$FIRST" =~ ^(WP|TSK)- ]]; then
    : # skip
  # 그 외 → 서브프로젝트 후보
  elif [ -d "docs/${FIRST}" ]; then
    SUBPROJECT="$FIRST"
    DOCS_DIR="docs/${FIRST}"
    IDX=1
  elif [ -z "$FIRST" ]; then
    : # empty
  else
    # docs/{FIRST}/ 없음 → 에러
    echo "{\"error\":\"docs/${FIRST}/ 디렉토리가 없습니다\"}" >&2
    exit 1
  fi
fi

# ── 2단계: 나머지 토큰 파싱 ──
while [ $IDX -lt ${#TOKENS[@]} ]; do
  TOK="${TOKENS[$IDX]}"
  case "$TOK" in
    --only)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_ONLY="${TOKENS[$IDX]}"
      ;;
    --model)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_MODEL="${TOKENS[$IDX]}"
      ;;
    --team-size)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_TEAM_SIZE="${TOKENS[$IDX]}"
      ;;
    --pool-size)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_POOL_SIZE="${TOKENS[$IDX]}"
      ;;
    --scale)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_SCALE="${TOKENS[$IDX]}"
      ;;
    --start-date)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_START_DATE="${TOKENS[$IDX]}"
      ;;
    --estimate-only)
      OPT_ESTIMATE_ONLY=true
      ;;
    --workdir)
      IDX=$((IDX+1))
      [ $IDX -lt ${#TOKENS[@]} ] && OPT_WORKDIR="${TOKENS[$IDX]}"
      ;;
    --leader)
      OPT_LEADER=true
      ;;
    --claim)
      OPT_CLAIM=true
      ;;
    TSK-*)
      TSK_ID="$TOK"
      ;;
    WP-*)
      WP_IDS+=("$TOK")
      ;;
    *)
      # 알 수 없는 토큰 — manifest 파일 경로일 수 있음
      if [ -f "$TOK" ]; then
        OPT_WORKDIR="$TOK"  # manifest path로 재사용
      fi
      ;;
  esac
  IDX=$((IDX+1))
done

# ── 3단계: WP_IDS → JSON array ──
WP_JSON="["
first=true
for wp in "${WP_IDS[@]+"${WP_IDS[@]}"}"; do
  $first && first=false || WP_JSON+=","
  WP_JSON+="\"$wp\""
done
WP_JSON+="]"

# ── 4단계: 출력 ──
cat <<JSONEOF
{
  "subproject": "$(json_escape "$SUBPROJECT")",
  "docs_dir": "$(json_escape "$DOCS_DIR")",
  "tsk_id": "$(json_escape "$TSK_ID")",
  "wp_ids": ${WP_JSON},
  "options": {
    "only": "$(json_escape "$OPT_ONLY")",
    "model": "$(json_escape "$OPT_MODEL")",
    "team_size": ${OPT_TEAM_SIZE},
    "pool_size": ${OPT_POOL_SIZE},
    "scale": "$(json_escape "$OPT_SCALE")",
    "start_date": "$(json_escape "$OPT_START_DATE")",
    "estimate_only": ${OPT_ESTIMATE_ONLY},
    "workdir": "$(json_escape "$OPT_WORKDIR")",
    "leader": ${OPT_LEADER},
    "claim": ${OPT_CLAIM}
  }
}
JSONEOF
