#!/usr/bin/env bash
# wp-setup.sh — WP별 worktree + 프롬프트 + tmux 셋업 자동화
# 팀리더가 JSON config를 생성하고 이 스크립트를 호출하면,
# 토큰 소비 없이 모든 파일 생성 + tmux spawn을 수행한다.
set -euo pipefail

CONFIG_FILE="${1:?Usage: wp-setup.sh <config.json>}"

# === Dependencies ===
for cmd in jq git; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: ${cmd} 필요" >&2; exit 1; }
done

# === Parse global config ===
rc() { jq -r "$1" "$CONFIG_FILE"; }

PROJECT_NAME=$(rc '.project_name')
WINDOW_SUFFIX=$(rc '.window_suffix // ""')
TEMP_DIR=$(rc '.temp_dir // "/tmp"')
SHARED_SIGNAL_DIR=$(rc '.shared_signal_dir')
DOCS_DIR=$(rc '.docs_dir // "docs"')
WBS_PATH=$(rc '.wbs_path')
SESSION=$(rc '.session')
MODEL_OVERRIDE=$(rc '.model_override // ""')
WORKER_MODEL=$(rc '.worker_model // "sonnet"')
WP_LEADER_MODEL=$(rc '.wp_leader_model // "sonnet"')
PLUGIN_ROOT=$(rc '.plugin_root')

DDTR_TEMPLATE="${PLUGIN_ROOT}/skills/dev-team/references/ddtr-prompt-template.md"
WP_LEADER_TEMPLATE="${PLUGIN_ROOT}/skills/dev-team/references/wp-leader-prompt.md"
WP_COUNT=$(jq '.wps | length' "$CONFIG_FILE")

# === Utility functions ===

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WBS_PARSE="${SCRIPT_DIR}/wbs-parse.sh"

# 템플릿 파일에서 외부 ``` 마커 사이의 내용을 추출
extract_template() {
  local file="$1"
  local first last
  first=$(grep -n '^```$' "$file" | head -1 | cut -d: -f1)
  last=$(grep -n '^```$' "$file" | tail -1 | cut -d: -f1)
  if [ -z "$first" ] || [ -z "$last" ] || [ "$first" -eq "$last" ]; then
    echo 'ERROR: 템플릿 ``` 마커 없음:' "$file" >&2; return 1
  fi
  sed -n "$((first+1)),$((last-1))p" "$file"
}

# wbs-parse.sh 위임: task 블록 추출
extract_task_block() {
  local wbs="$1" tsk="$2"
  bash "$WBS_PARSE" "$wbs" "$tsk" --block
}

# wbs-parse.sh 위임: task 필드 값 추출
get_task_field() {
  local wbs="$1" tsk="$2" field="$3"
  bash "$WBS_PARSE" "$wbs" "$tsk" --field "$field"
}

# {VAR} 플레이스홀더 치환 (awk)
# ⚠️ 핵심: 모든 시그널 경로는 SHARED_SIGNAL_DIR(프로젝트 레벨) 하나만 사용.
#    team-mode의 SIGNAL_DIR 기본값(per-window)과 혼동 방지.
substitute_vars() {
  local wp_id="${1:-}" team_size="${2:-}" wt_name="${3:-}" tsk_id="${4:-}"
  local model_display="${MODEL_OVERRIDE:-없음}"

  awk \
    -v WP_ID="$wp_id" \
    -v TEAM_SIZE="$team_size" \
    -v WT_NAME="$wt_name" \
    -v SIG_DIR="$SHARED_SIGNAL_DIR" \
    -v TMP_DIR="$TEMP_DIR" \
    -v DOC_DIR="$DOCS_DIR" \
    -v TSK_ID="$tsk_id" \
    -v MODEL_DISPLAY="$model_display" \
    -v SESSION_NAME="$SESSION" \
    -v WORKER_MDL="$WORKER_MODEL" \
    '{
      gsub(/{WP-ID}/, WP_ID)
      gsub(/{TEAM_SIZE}/, TEAM_SIZE)
      gsub(/{WT_NAME}/, WT_NAME)
      gsub(/{SHARED_SIGNAL_DIR}/, SIG_DIR)
      gsub(/{TEMP_DIR}/, TMP_DIR)
      gsub(/{DOCS_DIR}/, DOC_DIR)
      gsub(/{TSK-ID}/, TSK_ID)
      gsub(/{SESSION}/, SESSION_NAME)
      gsub(/{WORKER_MODEL}/, WORKER_MDL)
      if (index($0, "{MODEL_OVERRIDE") > 0)
        gsub(/{MODEL_OVERRIDE 또는 "없음"}/, MODEL_DISPLAY)
      print
    }'
}

# 멀티라인 블록 삽입 (플레이스홀더 라인을 파일 내용으로 교체)
insert_blocks() {
  local block1_marker="$1" block1_file="$2"
  local block2_marker="${3:-}" block2_file="${4:-}"

  awk -v m1="$block1_marker" -v f1="$block1_file" \
      -v m2="$block2_marker" -v f2="$block2_file" '
    index($0, m1) > 0 && m1 != "" {
      while ((getline line < f1) > 0) print line; close(f1); next
    }
    index($0, m2) > 0 && m2 != "" {
      while ((getline line < f2) > 0) print line; close(f2); next
    }
    { print }
  '
}

# === 템플릿 캐싱 (1회) ===
DDTR_RAW=$(extract_template "$DDTR_TEMPLATE")
WP_LEADER_RAW=$(extract_template "$WP_LEADER_TEMPLATE")

# MODEL_OVERRIDE 선언 (DDTR 프롬프트 앞에 붙임)
DDTR_PREFIX=""
if [ -n "$MODEL_OVERRIDE" ]; then
  DDTR_PREFIX="⚠️ MODEL_OVERRIDE = \"${MODEL_OVERRIDE}\" — 아래 모든 Phase의 model 파라미터에 이 값을 사용하라."$'\n\n'
fi

# === Main loop ===
for ((i=0; i<WP_COUNT; i++)); do
  WP_ID=$(jq -r ".wps[$i].wp_id" "$CONFIG_FILE")
  TEAM_SIZE=$(jq -r ".wps[$i].team_size // 3" "$CONFIG_FILE")
  EXECUTION_PLAN=$(jq -r ".wps[$i].execution_plan" "$CONFIG_FILE")

  TASKS=()
  while IFS= read -r t; do TASKS+=("$t"); done < <(jq -r ".wps[$i].tasks[]" "$CONFIG_FILE")

  WT_NAME="${WP_ID}${WINDOW_SUFFIX}"

  echo "=== [${WP_ID}] 셋업 시작 ==="

  # --- 1. Worktree ---
  RESUME_MODE=false
  if [ -d ".claude/worktrees/${WT_NAME}" ] && git branch --list "dev/${WT_NAME}" | grep -q .; then
    echo "[${WP_ID}] worktree: 재개 (.claude/worktrees/${WT_NAME})"
    RESUME_MODE=true
  else
    git worktree add ".claude/worktrees/${WT_NAME}" -b "dev/${WT_NAME}" 2>&1
    echo "[${WP_ID}] worktree: 생성 (.claude/worktrees/${WT_NAME})"
  fi

  # --- 2. Signal dir + 복원 ---
  # ⚠️ 모든 WP가 동일한 SHARED_SIGNAL_DIR을 사용.
  #    per-WP 시그널 디렉토리를 별도로 만들지 않는다.
  mkdir -p "${SHARED_SIGNAL_DIR}"

  if [ "$RESUME_MODE" = true ]; then
    for WT_DIR in .claude/worktrees/*/; do
      [ -f "${WT_DIR}${DOCS_DIR}/wbs.md" ] || continue
      grep -oE 'TSK-[0-9]+(-[0-9]+)+' "${WT_DIR}${DOCS_DIR}/wbs.md" 2>/dev/null | sort -u | while read -r TSK; do
        if grep -q "\[xx\]" <<< "$(grep "$TSK" "${WT_DIR}${DOCS_DIR}/wbs.md" 2>/dev/null)"; then
          [ ! -f "${SHARED_SIGNAL_DIR}/${TSK}.done" ] && echo "resumed" > "${SHARED_SIGNAL_DIR}/${TSK}.done"
        fi
      done
    done
    for f in "${SHARED_SIGNAL_DIR}"/*.running; do
      [ -f "$f" ] && rm -f "$f"
    done
    rm -f "${SHARED_SIGNAL_DIR}/${WT_NAME}.initialized"
    echo "[${WP_ID}] signals: 복원 완료 (${SHARED_SIGNAL_DIR})"
  fi

  # --- 3. DDTR 프롬프트 생성 + 데이터 수집 ---
  DDTR_FILES=()
  MANIFEST_TASKS=""
  ALL_TASK_BLOCKS=""

  for TSK_ID in "${TASKS[@]}"; do
    STATUS=$(get_task_field "$WBS_PATH" "$TSK_ID" "status")
    [[ "$STATUS" == *"[xx]"* ]] && continue

    DEPENDS=$(get_task_field "$WBS_PATH" "$TSK_ID" "depends")
    [ -z "$DEPENDS" ] && DEPENDS="(none)"
    TASK_BLOCK=$(extract_task_block "$WBS_PATH" "$TSK_ID")

    ALL_TASK_BLOCKS+="${TASK_BLOCK}"$'\n\n'

    # DDTR 프롬프트 생성 (기존 파일 있으면 재사용)
    DDTR_OUT="${TEMP_DIR}/task-${TSK_ID}.txt"
    if [ -f "$DDTR_OUT" ]; then
      echo "[${WP_ID}] ddtr: ${TSK_ID} 재사용 (${DDTR_OUT})"
    else
      TB_TMP="${TEMP_DIR}/.tb-${TSK_ID}.tmp"
      printf '%s\n' "$TASK_BLOCK" > "$TB_TMP"
      printf '%s%s\n' "$DDTR_PREFIX" "$DDTR_RAW" | \
        substitute_vars "$WP_ID" "$TEAM_SIZE" "$WT_NAME" "$TSK_ID" | \
        insert_blocks "{단일 Task 블록" "$TB_TMP" > "${DDTR_OUT}.tmp"
      mv "${DDTR_OUT}.tmp" "$DDTR_OUT"
      rm -f "$TB_TMP"
    fi

    DDTR_FILES+=("${TSK_ID}")

    MANIFEST_TASKS+="
### ${TSK_ID}
- status: ${STATUS}
- depends: ${DEPENDS}
- prompt_file: ${TEMP_DIR}/task-${TSK_ID}.txt
"
  done

  echo "[${WP_ID}] ddtr: ${DDTR_FILES[*]:-없음}"

  # 모든 Task [xx]이면 스킵
  if [ ${#DDTR_FILES[@]} -eq 0 ]; then
    echo "[${WP_ID}] 모든 Task [xx] — 스킵"
    echo "all tasks already [xx]" > "${SHARED_SIGNAL_DIR}/${WT_NAME}.done"
    continue
  fi

  # --- 4. Manifest ---
  # ⚠️ signal_dir = SHARED_SIGNAL_DIR (프로젝트 레벨).
  #    WP 리더가 team-mode를 읽을 때 이 값을 SIGNAL_DIR로 사용해야 한다.
  MANIFEST_PATH="${TEMP_DIR}/team-manifest-${WT_NAME}.md"
  cat > "${MANIFEST_PATH}" << MANIFEST_EOF
# Configuration
- team_size: ${TEAM_SIZE}
- window_name: ${WT_NAME}
- signal_dir: ${SHARED_SIGNAL_DIR}
- docs_dir: ${DOCS_DIR}
- worker_model: ${WORKER_MODEL}

## Tasks
${MANIFEST_TASKS}
MANIFEST_EOF
  echo "[${WP_ID}] manifest: ${MANIFEST_PATH}"

  # --- 5. WP 리더 프롬프트 (기존 파일 있으면 재사용) ---
  WP_LEADER_OUT=".claude/worktrees/${WT_NAME}-prompt.txt"
  if [ -f "$WP_LEADER_OUT" ]; then
    echo "[${WP_ID}] leader: 재사용 (${WP_LEADER_OUT})"
  else
    TASKS_TMP="${TEMP_DIR}/.tasks-${WT_NAME}.tmp"
    PLAN_TMP="${TEMP_DIR}/.plan-${WT_NAME}.tmp"
    printf '%s\n' "$ALL_TASK_BLOCKS" > "$TASKS_TMP"
    printf '%s\n' "$EXECUTION_PLAN" > "$PLAN_TMP"

    printf '%s\n' "$WP_LEADER_RAW" | \
      substitute_vars "$WP_ID" "$TEAM_SIZE" "$WT_NAME" "" | \
      insert_blocks \
        "[WP 내 모든 Task 블록" "$TASKS_TMP" \
        "[팀리더가 산출한 레벨별 실행 계획]" "$PLAN_TMP" \
      > "${WP_LEADER_OUT}.tmp"
    mv "${WP_LEADER_OUT}.tmp" "$WP_LEADER_OUT"
    rm -f "$TASKS_TMP" "$PLAN_TMP"
    echo "[${WP_ID}] leader: ${WP_LEADER_OUT}"
  fi

  # --- 6. Runner + tmux spawn ---
  RUNNER=".claude/worktrees/${WT_NAME}-run.sh"
  cat > "$RUNNER" << RUNNER_EOF
#!/bin/bash
cd "\$(dirname "\$0")/${WT_NAME}"
exec claude --dangerously-skip-permissions --model ${WP_LEADER_MODEL} "\$(<../${WT_NAME}-prompt.txt)"
RUNNER_EOF
  chmod +x "$RUNNER"

  if [ -n "${SESSION:-}" ] && [ -n "$TMUX" ]; then
    tmux new-window -t "${SESSION}:" -n "${WT_NAME}" "$RUNNER"
    tmux set-option -w -t "${SESSION}:${WT_NAME}" automatic-rename off
    tmux set-option -w -t "${SESSION}:${WT_NAME}" allow-rename off
    tmux set-option -w -t "${SESSION}:${WT_NAME}" pane-border-status top
    tmux set-option -w -t "${SESSION}:${WT_NAME}" pane-border-format " #{pane_title} "

    # Worker pane 사전 생성 (리더 초기화 부담 제거 + interrupt 취약점 해소)
    WT_ABS_PATH="$(pwd)/.claude/worktrees/${WT_NAME}"
    for wi in $(seq 1 ${TEAM_SIZE}); do
      tmux split-window -t "${SESSION}:${WT_NAME}" -h \
        "cd '${WT_ABS_PATH}' && claude --dangerously-skip-permissions --model ${WORKER_MODEL}"
    done
    tmux select-layout -t "${SESSION}:${WT_NAME}" tiled

    # Pane ID 파일 생성 (리더가 참조)
    PANE_IDS_FILE="${TEMP_DIR}/pane-ids-${WT_NAME}.txt"
    tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_index}:#{pane_id}' > "${PANE_IDS_FILE}"

    # Pane 타이틀 설정
    PANE0_ID=$(awk -F: '$1=="0" {print $2}' "${PANE_IDS_FILE}")
    tmux select-pane -t "${PANE0_ID}" -T "${WP_ID} Leader"
    for wi in $(seq 1 ${TEAM_SIZE}); do
      WI_PANE_ID=$(awk -F: -v idx="$wi" '$1==idx {print $2}' "${PANE_IDS_FILE}")
      [ -n "${WI_PANE_ID}" ] && tmux select-pane -t "${WI_PANE_ID}" -T "worker${wi} idle"
    done

    echo "[${WP_ID}] spawn: tmux window ${WT_NAME} (leader + ${TEAM_SIZE} workers)"
  else
    echo "[${WP_ID}] runner: ${RUNNER} (tmux 없음 — 수동 실행 필요)"
  fi

  echo "=== [${WP_ID}] 셋업 완료 ==="
done

echo ""
echo "전체 셋업 완료: ${WP_COUNT}개 WP"
echo "시그널 디렉토리: ${SHARED_SIGNAL_DIR}"
