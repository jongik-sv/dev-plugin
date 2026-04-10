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
  --dev-config           Extract ## Dev Config section as JSON

Examples:
  wbs-parse.py docs/wbs.md TSK-01-02
  wbs-parse.py docs/wbs.md TSK-01-02 --block
  wbs-parse.py docs/wbs.md TSK-01-02 --field domain
  wbs-parse.py docs/wbs.md WP-01 --tasks
  wbs-parse.py docs/wbs.md WP-01 --tasks-pending
  wbs-parse.py docs/wbs.md - --resumable-wps
  wbs-parse.py docs/wbs.md TSK-01-02 --phase-start
  wbs-parse.py docs/wbs.md - --dev-config
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


DEV_CONFIG_TEMPLATE = """\
wbs.md에 '## Dev Config' 섹션이 없습니다. 아래 내용을 wbs.md 헤더와 첫 번째 WP 사이에 추가하세요:

## Dev Config

### Domains
| domain | description | unit-test | e2e-test |
|--------|-------------|-----------|----------|
| backend | Server API | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| frontend | Client UI | `your-unit-test-cmd` | `your-e2e-test-cmd` |
| database | Data layer | - | - |
| fullstack | Full stack | - | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| backend | Your backend architecture description |
| frontend | Your frontend architecture description |

### Cleanup Processes
node, vitest
"""


def _parse_md_table(lines: list, header_name: str, expected_cols: list) -> list:
    """Parse a markdown table under a ### heading. Handles backtick-wrapped values containing |."""
    in_section = False
    header_found = False
    rows = []

    for line in lines:
        stripped = line.strip()
        # Match ### heading
        if re.match(r'^###\s+' + re.escape(header_name) + r'\s*$', stripped, re.IGNORECASE):
            in_section = True
            header_found = False
            continue
        # Exit on next ### or ## heading
        if in_section and re.match(r'^#{2,3}\s+', stripped) and not re.match(r'^###\s+' + re.escape(header_name), stripped, re.IGNORECASE):
            break
        if not in_section:
            continue

        # Skip empty lines
        if not stripped or not stripped.startswith("|"):
            continue

        # Parse table row — handle backticks containing |
        cells = _split_table_row(stripped)
        if not cells:
            continue

        # Skip header row and separator row
        if not header_found:
            header_found = True
            continue
        if all(c.strip().replace("-", "").replace(":", "") == "" for c in cells):
            continue

        rows.append(cells)

    return rows


def _split_table_row(row: str) -> list:
    """Split a markdown table row, respecting backtick-wrapped content."""
    # Remove leading/trailing |
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]

    cells = []
    current = []
    in_backtick = False
    for ch in row:
        if ch == '`':
            in_backtick = not in_backtick
            current.append(ch)
        elif ch == '|' and not in_backtick:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    cells.append("".join(current).strip())
    return cells


def _cell_value(cell: str):
    """Convert cell value: strip backticks, '-' → None."""
    cell = cell.strip()
    if cell == "-" or cell == "":
        return None
    # Strip surrounding backticks
    if cell.startswith("`") and cell.endswith("`"):
        cell = cell[1:-1]
    return cell


def parse_dev_config(wbs_text: str) -> dict:
    """Parse ## Dev Config section from WBS text."""
    lines = wbs_text.splitlines()
    start = None
    end = None

    for i, line in enumerate(lines):
        if re.match(r'^##\s+Dev\s+Config\s*$', line, re.IGNORECASE):
            start = i
            continue
        # End at next ## heading (not ###)
        if start is not None and re.match(r'^##\s+', line) and not line.strip().startswith("###"):
            if not re.match(r'^##\s+Dev\s+Config', line, re.IGNORECASE):
                end = i
                break

    if start is None:
        return {"error": "DEV_CONFIG_MISSING", "message": DEV_CONFIG_TEMPLATE}

    section = lines[start:end]

    # Parse Domains table
    domain_rows = _parse_md_table(section, "Domains", ["domain", "description", "unit-test", "e2e-test"])
    domains = {}
    fullstack_domains = []
    for row in domain_rows:
        if len(row) < 4:
            continue
        d = row[0].strip().strip("`")
        unit = _cell_value(row[2])
        e2e = _cell_value(row[3])
        domains[d] = {
            "description": _cell_value(row[1]) or d,
            "unit_test": unit,
            "e2e_test": e2e,
        }
        if d != "fullstack" and (unit or e2e):
            fullstack_domains.append(d)

    # Parse Design Guidance table
    guidance_rows = _parse_md_table(section, "Design Guidance", ["domain", "architecture"])
    design_guidance = {}
    for row in guidance_rows:
        if len(row) < 2:
            continue
        d = row[0].strip().strip("`")
        val = _cell_value(row[1])
        if val:
            design_guidance[d] = val

    # Parse Cleanup Processes
    cleanup_processes = []
    in_cleanup = False
    for line in section:
        stripped = line.strip()
        if re.match(r'^###\s+Cleanup\s+Processes\s*$', stripped, re.IGNORECASE):
            in_cleanup = True
            continue
        if in_cleanup and re.match(r'^#{2,3}\s+', stripped):
            break
        if in_cleanup and stripped and not stripped.startswith("|") and not stripped.startswith("---"):
            cleanup_processes = [p.strip() for p in stripped.split(",") if p.strip()]
            break

    return {
        "domains": domains,
        "design_guidance": design_guidance,
        "cleanup_processes": cleanup_processes,
        "fullstack_domains": fullstack_domains,
    }


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

    # -- Dev Config --
    elif mode == "--dev-config":
        result = parse_dev_config(wbs_text)
        print(json.dumps(result, ensure_ascii=False, indent=2))

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
