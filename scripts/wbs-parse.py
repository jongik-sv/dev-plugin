#!/usr/bin/env python3
"""wbs-parse.py — Extract Task/WP information from WBS file as structured output.

Replaces wbs-parse.sh for cross-platform support.
Output format is identical JSON.
"""
import sys
import os
import re
import json

USAGE = """\
Usage: wbs-parse.py <wbs-path> <ID> [mode]

Modes:
  (default)              Task/WP full fields as JSON
  --block                Task block raw text
  --field <name>         Single field value
  --tasks                WP child Task list (JSON array)
  --tasks-pending        WP child incomplete Tasks only (status != [xx])
  --resumable-wps        Executable WP list (WPs with incomplete Tasks)
  --phase-start          Start phase based on Task's current status

Examples:
  wbs-parse.py docs/wbs.md TSK-01-02
  wbs-parse.py docs/wbs.md TSK-01-02 --block
  wbs-parse.py docs/wbs.md TSK-01-02 --field domain
  wbs-parse.py docs/wbs.md WP-01 --tasks
  wbs-parse.py docs/wbs.md WP-01 --tasks-pending
  wbs-parse.py docs/wbs.md - --resumable-wps
  wbs-parse.py docs/wbs.md TSK-01-02 --phase-start
"""


def json_escape(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    return s


def extract_task_block(wbs_text: str, tsk_id: str) -> str:
    """Extract a task block (### or #### level) from WBS text."""
    lines = wbs_text.splitlines()
    result = []
    found = False
    level = 0

    for line in lines:
        # Calculate heading level
        hl = 0
        for ch in line:
            if ch == "#":
                hl += 1
            else:
                break

        # Match target TSK heading
        if not found and hl >= 2 and f"{tsk_id}:" in line:
            found = True
            level = hl
            result.append(line)
            continue

        # End at same or higher level heading
        if found and hl >= 2 and hl <= level and f"{tsk_id}:" not in line:
            break

        if found:
            result.append(line)

    return "\n".join(result)


def extract_wp_block(wbs_text: str, wp_id: str) -> str:
    """Extract a WP block (## level) from WBS text."""
    lines = wbs_text.splitlines()
    result = []
    found = False

    for line in lines:
        if line.startswith("## ") and f"{wp_id}:" in line:
            found = True
            result.append(line)
            continue
        if found and line.startswith("## "):
            break
        if found:
            result.append(line)

    return "\n".join(result)


def get_field(block: str, field_name: str) -> str:
    """Extract a single field value from a block."""
    for line in block.splitlines():
        pattern = f"- {field_name}:"
        if line.startswith(pattern):
            return line[len(pattern):].strip()
    return ""


def parse_tasks_from_wp(wp_block: str, pending_only: bool = False) -> list:
    """Parse task entries from a WP block."""
    tasks = []
    current = None

    for line in wp_block.splitlines():
        m = re.match(r'^#{3,4}\s+(TSK-\d+(?:-\d+)+):', line)
        if m:
            if current is not None:
                if not pending_only or "[xx]" not in current.get("status", ""):
                    tasks.append(current)
            current = {
                "tsk_id": m.group(1),
                "status": "",
                "depends": "",
                "domain": "",
            }
            continue
        if current is not None:
            if line.startswith("- status:"):
                current["status"] = line[len("- status:"):].strip()
            elif line.startswith("- depends:"):
                current["depends"] = line[len("- depends:"):].strip()
            elif line.startswith("- domain:"):
                current["domain"] = line[len("- domain:"):].strip()

    if current is not None:
        if not pending_only or "[xx]" not in current.get("status", ""):
            tasks.append(current)

    return tasks


def main():
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    wbs_path = sys.argv[1]
    target_id = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--json"
    field_name = sys.argv[4] if mode == "--field" and len(sys.argv) > 4 else None

    if mode == "--field" and not field_name:
        print("ERROR: --field requires a field name", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(wbs_path):
        print(f"ERROR: file not found: {wbs_path}", file=sys.stderr)
        sys.exit(1)

    with open(wbs_path, "r", encoding="utf-8") as f:
        wbs_text = f.read()

    # -- Raw block --
    if mode == "--block":
        block = extract_task_block(wbs_text, target_id)
        if not block:
            print(f"ERROR: {target_id} not found in {wbs_path}", file=sys.stderr)
            sys.exit(1)
        print(block)

    # -- Single field --
    elif mode == "--field":
        block = extract_task_block(wbs_text, target_id)
        if not block:
            print(f"ERROR: {target_id} not found", file=sys.stderr)
            sys.exit(1)
        print(get_field(block, field_name))

    # -- Task JSON (default) --
    elif mode == "--json":
        block = extract_task_block(wbs_text, target_id)
        if not block:
            print(f"ERROR: {target_id} not found in {wbs_path}", file=sys.stderr)
            sys.exit(1)

        first_line = block.splitlines()[0] if block else ""
        # Remove heading prefix and task ID
        title = re.sub(r'^#{2,4}\s+[^:]*:\s*', '', first_line)

        result = {
            "tsk_id": target_id,
            "title": title,
            "category": get_field(block, "category"),
            "domain": get_field(block, "domain"),
            "status": get_field(block, "status"),
            "priority": get_field(block, "priority"),
            "assignee": get_field(block, "assignee"),
            "schedule": get_field(block, "schedule"),
            "tags": get_field(block, "tags"),
            "depends": get_field(block, "depends"),
            "block": block,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # -- WP child tasks (all) --
    elif mode == "--tasks":
        wp_block = extract_wp_block(wbs_text, target_id)
        if not wp_block:
            print(f"ERROR: {target_id} not found in {wbs_path}", file=sys.stderr)
            sys.exit(1)
        tasks = parse_tasks_from_wp(wp_block, pending_only=False)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    # -- WP child tasks (pending only) --
    elif mode == "--tasks-pending":
        wp_block = extract_wp_block(wbs_text, target_id)
        if not wp_block:
            print(f"ERROR: {target_id} not found in {wbs_path}", file=sys.stderr)
            sys.exit(1)
        tasks = parse_tasks_from_wp(wp_block, pending_only=True)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    # -- Resumable WPs --
    elif mode == "--resumable-wps":
        wps = []
        current_wp = None
        in_task = False

        for line in wbs_text.splitlines():
            m = re.match(r'^## (WP-\d+):', line)
            if m:
                if current_wp and current_wp["pending"] > 0:
                    wps.append(current_wp)
                current_wp = {"wp_id": m.group(1), "pending": 0, "total": 0}
                in_task = False
                continue
            if current_wp is not None:
                if re.match(r'^#{3,4}\s+TSK-', line):
                    in_task = True
                    current_wp["total"] += 1
                if in_task and line.startswith("- status:"):
                    if "[xx]" not in line:
                        current_wp["pending"] += 1
                    in_task = False

        if current_wp and current_wp["pending"] > 0:
            wps.append(current_wp)

        print(json.dumps(wps, ensure_ascii=False, indent=2))

    # -- Phase start --
    elif mode == "--phase-start":
        block = extract_task_block(wbs_text, target_id)
        if not block:
            print(f"ERROR: {target_id} not found", file=sys.stderr)
            sys.exit(1)

        status = get_field(block, "status")
        domain = get_field(block, "domain")
        docs_dir = os.path.dirname(wbs_path)

        if "[xx]" in status:
            phase = "done"
        elif "[im]" in status:
            phase = "test"
        elif "[dd]" in status:
            design_path = os.path.join(docs_dir, "tasks", target_id, "design.md")
            phase = "build" if os.path.isfile(design_path) else "design"
        else:
            phase = "design"

        result = {
            "tsk_id": target_id,
            "status": status,
            "domain": domain,
            "start_phase": phase,
            "docs_dir": docs_dir,
        }
        print(json.dumps(result, ensure_ascii=False))

    else:
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
