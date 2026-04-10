#!/usr/bin/env python3
"""wbs-update-status.py — Update a Task's status field in wbs.md.

Finds the Task block by TSK-ID and replaces the `- status: [...]` line
regardless of the current status value (no hardcoded old-state assumption).

Usage: wbs-update-status.py <wbs-path> <TSK-ID> <new-status-code>

  new-status-code: status code without brackets — dd | im | xx | " " (space = not started)

Examples:
  wbs-update-status.py docs/wbs.md TSK-01-02 dd
  wbs-update-status.py docs/wbs.md TSK-01-02 im
  wbs-update-status.py docs/wbs.md TSK-01-02 xx

Output (JSON):
  {"tsk_id": "TSK-01-02", "old_status": "[ ]", "new_status": "[dd]", "updated": true}
"""
import sys
import os
import re
import json


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    wbs_path = sys.argv[1]
    tsk_id = sys.argv[2]
    new_code = sys.argv[3]

    if not os.path.isfile(wbs_path):
        print(json.dumps({"error": f"file not found: {wbs_path}"}))
        sys.exit(1)

    new_status = f"[{new_code}]"

    with open(wbs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_block = False
    block_level = 0
    old_status = None
    updated_lines = []
    updated = False

    for line in lines:
        stripped = line.rstrip("\n")

        # Detect heading level
        hl = 0
        for ch in stripped:
            if ch == "#":
                hl += 1
            else:
                break

        # Enter task block
        if not in_block and hl >= 3 and f"{tsk_id}:" in stripped:
            in_block = True
            block_level = hl
            updated_lines.append(line)
            continue

        # Exit task block at same or higher heading level
        if in_block and hl >= 2 and hl <= block_level and f"{tsk_id}:" not in stripped:
            in_block = False

        # Replace status line within the block (first occurrence only)
        if in_block and not updated and re.match(r"^- status:\s*\[", stripped):
            m = re.match(r"^(- status:\s*)(\[.*?\])", stripped)
            if m:
                old_status = m.group(2)
                new_line = line.replace(m.group(2), new_status, 1)
                updated_lines.append(new_line)
                updated = True
                continue

        updated_lines.append(line)

    if not updated:
        result = {
            "tsk_id": tsk_id,
            "error": f"{tsk_id} not found or status line missing in {wbs_path}",
            "updated": False,
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    with open(wbs_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    result = {
        "tsk_id": tsk_id,
        "old_status": old_status,
        "new_status": new_status,
        "updated": True,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
