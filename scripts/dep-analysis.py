#!/usr/bin/env python3
"""dep-analysis.py — Task dependency level calculation (topological sort).

Replaces dep-analysis.sh for cross-platform support.
Output format is identical JSON.
"""
import sys
import os
import json
import re

USAGE = """\
Usage: dep-analysis.py [input-file]

Input: JSON array (stdin or file), each element:
  {"tsk_id":"TSK-01-01", "depends":"-", "status":"[ ]"}
  Also accepts "id" as alias for "tsk_id" (e.g. agent-pool format)

  - depends: "-", "(none)", "" -> no dependency
  - depends: "TSK-01-01" or "TSK-01-01, TSK-01-02" -> comma separated
  - status "[xx]" tasks are treated as completed

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
  wbs-parse.py docs/wbs.md WP-01 --tasks-pending | python3 dep-analysis.py
  python3 dep-analysis.py /tmp/tasks.json
"""


def main():
    # Read input
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        input_path = sys.argv[1]
        if not os.path.isfile(input_path):
            print(f"ERROR: file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        with open(input_path, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    raw = raw.strip()
    if not raw:
        print(json.dumps({"levels": {}, "completed": [], "circular": [], "total": 0, "pending": 0}))
        sys.exit(0)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    completed = []
    is_completed = set()
    tasks = []  # ordered list of pending task IDs
    task_exists = set()
    dep_map = {}  # tsk_id -> list of dependency IDs

    for item in items:
        tsk_id = item.get("tsk_id", "") or item.get("id", "")
        status = item.get("status", "")
        dep_str = item.get("depends", "")

        if "[xx]" in status:
            completed.append(tsk_id)
            is_completed.add(tsk_id)
            continue

        tasks.append(tsk_id)
        task_exists.add(tsk_id)

        # Parse depends
        if not dep_str or dep_str in ("-", "(none)"):
            dep_map[tsk_id] = []
        else:
            deps = []
            for part in re.split(r'[,\s]+', dep_str):
                part = part.strip()
                if part and part != "-":
                    deps.append(part)
            dep_map[tsk_id] = deps

    # Topological sort — level assignment
    levels = {}
    level_assigned = set()
    assigned = 0
    max_iter = len(tasks) + 1
    current_level = 0
    circular = []

    while assigned < len(tasks) and current_level < max_iter:
        level_tasks = []

        for t in tasks:
            if t in level_assigned:
                continue

            # Check all dependencies met
            all_met = True
            for dep in dep_map.get(t, []):
                if dep in is_completed:
                    continue
                if dep in level_assigned:
                    continue
                if dep not in task_exists:
                    continue  # external dependency — assume satisfied
                all_met = False
                break

            if all_met:
                level_tasks.append(t)

        if not level_tasks and assigned < len(tasks):
            # Circular dependency detected
            for t in tasks:
                if t not in level_assigned:
                    circular.append(t)
                    level_assigned.add(t)
                    assigned += 1
            break

        levels[str(current_level)] = level_tasks
        for t in level_tasks:
            level_assigned.add(t)
            assigned += 1

        current_level += 1

    result = {
        "levels": levels,
        "completed": completed,
        "circular": circular,
        "total": len(tasks) + len(completed),
        "pending": len(tasks),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
