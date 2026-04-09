#!/usr/bin/env bash
# dep-analysis.sh — Task 의존성 레벨 계산 (위상 정렬)
# 목적: LLM이 그래프 알고리즘을 실행하는 대신 스크립트로 처리 → 토큰 절약
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: dep-analysis.sh [input-file]

Input: JSON array (stdin or file), each element:
  {"tsk_id":"TSK-01-01", "depends":"-", "status":"[ ]"}

  - depends: "-", "(none)", "" → 의존 없음
  - depends: "TSK-01-01" 또는 "TSK-01-01, TSK-01-02" → 쉼표 구분
  - status가 "[xx]"인 task는 이미 완료로 간주

Output: JSON with execution levels
  {
    "levels": {
      "0": ["TSK-01-01", "TSK-01-03"],
      "1": ["TSK-01-02"],
      "2": ["TSK-01-04"]
    },
    "completed": ["TSK-01-00"],
    "circular": [],
    "total": 4,
    "pending": 3
  }

Examples:
  # wbs-parse.sh 출력을 파이프
  wbs-parse.sh docs/wbs.md WP-01 --tasks-pending | dep-analysis.sh

  # 파일에서 읽기
  dep-analysis.sh /tmp/tasks.json
EOF
  exit 1
}

# ──────────────────────────────────────────────
# Input
# ──────────────────────────────────────────────
if [ $# -gt 0 ] && [ "$1" != "-" ]; then
  [ ! -f "$1" ] && { echo "ERROR: file not found: $1" >&2; exit 1; }
  INPUT=$(cat "$1")
else
  INPUT=$(cat)
fi

[ -z "$INPUT" ] && { echo '{"levels":{},"completed":[],"circular":[],"total":0,"pending":0}'; exit 0; }

# ──────────────────────────────────────────────
# awk로 위상 정렬 수행
# ──────────────────────────────────────────────
echo "$INPUT" | awk '
BEGIN {
  task_count = 0
  completed_count = 0
}

# JSON 파싱 (간이): tsk_id, depends, status 추출
{
  # 한 줄씩 처리 — JSON array를 줄 단위로 분해
  line = $0

  # tsk_id 추출
  if (match(line, /"tsk_id":"[^"]*"/)) {
    s = substr(line, RSTART, RLENGTH)
    gsub(/"tsk_id":"/, "", s); gsub(/"/, "", s)
    tsk_id = s
  } else { next }

  # status 추출
  status = ""
  if (match(line, /"status":"[^"]*"/)) {
    s = substr(line, RSTART, RLENGTH)
    gsub(/"status":"/, "", s); gsub(/"/, "", s)
    status = s
  }

  # [xx] → completed 목록에 추가, 레벨 계산에서 제외
  if (index(status, "[xx]") > 0) {
    completed[completed_count++] = tsk_id
    is_completed[tsk_id] = 1
    next
  }

  # depends 추출
  dep_str = ""
  if (match(line, /"depends":"[^"]*"/)) {
    s = substr(line, RSTART, RLENGTH)
    gsub(/"depends":"/, "", s); gsub(/"/, "", s)
    dep_str = s
  }

  # task 등록
  tasks[task_count] = tsk_id
  task_exists[tsk_id] = 1
  task_count++

  # depends 파싱 (쉼표 구분)
  if (dep_str == "" || dep_str == "-" || dep_str == "(none)") {
    dep_count[tsk_id] = 0
  } else {
    n = split(dep_str, parts, /[,[:space:]]+/)
    dc = 0
    for (i = 1; i <= n; i++) {
      d = parts[i]
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", d)
      if (d != "" && d != "-") {
        deps[tsk_id, dc] = d
        dc++
      }
    }
    dep_count[tsk_id] = dc
  }
}

END {
  # 레벨 계산
  max_iter = task_count + 1
  iter = 0
  assigned = 0

  while (assigned < task_count && iter < max_iter) {
    level_tasks = ""
    level_count = 0

    for (i = 0; i < task_count; i++) {
      t = tasks[i]
      if (t in level_assigned) continue

      # 의존성 확인
      all_met = 1
      for (d = 0; d < dep_count[t]; d++) {
        dep = deps[t, d]
        # 완료된 task이거나 이전 레벨에서 할당됨 → OK
        # WP 외부 task(task_exists에 없음) → 완료 간주
        if (dep in is_completed) continue
        if (dep in level_assigned) continue
        if (!(dep in task_exists)) continue  # 외부 의존 → 이미 충족 가정
        all_met = 0
        break
      }

      if (all_met) {
        if (level_count > 0) level_tasks = level_tasks ","
        level_tasks = level_tasks "\"" t "\""
        pending_level[t] = iter
        level_count++
      }
    }

    if (level_count == 0 && assigned < task_count) {
      # 순환 의존 감지
      for (i = 0; i < task_count; i++) {
        t = tasks[i]
        if (!(t in level_assigned)) {
          if (circular_count > 0) circular_str = circular_str ","
          circular_str = circular_str "\"" t "\""
          circular_count++
          level_assigned[t] = 1
          assigned++
        }
      }
      break
    }

    # 이번 레벨 확정
    levels[iter] = level_tasks
    # level_assigned에 추가
    for (i = 0; i < task_count; i++) {
      t = tasks[i]
      if ((t in pending_level) && pending_level[t] == iter) {
        level_assigned[t] = 1
        assigned++
      }
    }

    iter++
  }

  max_level = iter

  # JSON 출력
  printf "{\n"

  # levels
  printf "  \"levels\": {\n"
  first_level = 1
  for (l = 0; l < max_level; l++) {
    if (levels[l] == "") continue
    if (!first_level) printf ",\n"
    printf "    \"%d\": [%s]", l, levels[l]
    first_level = 0
  }
  printf "\n  },\n"

  # completed
  printf "  \"completed\": ["
  for (i = 0; i < completed_count; i++) {
    if (i > 0) printf ","
    printf "\"%s\"", completed[i]
  }
  printf "],\n"

  # circular
  printf "  \"circular\": ["
  if (circular_str != "") printf "%s", circular_str
  printf "],\n"

  # counts
  printf "  \"total\": %d,\n", task_count + completed_count
  printf "  \"pending\": %d\n", task_count

  printf "}\n"
}
'
