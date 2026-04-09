#!/usr/bin/env python3
"""args-parse.py — Skill argument parsing (subproject detection + option extraction).

Replaces args-parse.sh for cross-platform support.
Output format is identical JSON.
"""
import sys
import os
import json
import shlex

USAGE = """\
Usage: args-parse.py <skill> [arguments...]

Skills: dev, dev-design, dev-build, dev-test, dev-refactor, dev-team, wbs

Output: JSON with parsed arguments
  {
    "subproject": "",
    "docs_dir": "docs",
    "tsk_id": "TSK-01-02",
    "wp_ids": ["WP-01"],
    "options": {
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
  args-parse.py dev "p1 TSK-01-01 --only design"
  args-parse.py dev-team "p1 WP-01 WP-02 --team-size 5 --model opus"
  args-parse.py wbs "p1 --scale large --start-date 2026-04-01"
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    skill = sys.argv[1]
    args_str = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    # Parse
    subproject = ""
    docs_dir = "docs"
    tsk_id = ""
    wp_ids = []
    opt_only = ""
    opt_model = ""
    opt_team_size = 3
    opt_pool_size = 5
    opt_scale = ""
    opt_start_date = ""
    opt_estimate_only = False
    opt_workdir = ""
    opt_leader = False
    opt_claim = False

    tokens = args_str.split() if args_str.strip() else []
    idx = 0

    # Step 1: Subproject detection
    if tokens:
        first = tokens[0]
        if first.startswith("--"):
            pass  # option, not subproject
        elif first.startswith("WP-") or first.startswith("TSK-"):
            pass  # ID, not subproject
        elif os.path.isdir(os.path.join("docs", first)):
            subproject = first
            docs_dir = f"docs/{first}"
            idx = 1
        elif first == "":
            pass
        else:
            print(json.dumps({"error": f"docs/{first}/ \ub514\ub809\ud1a0\ub9ac\uac00 \uc5c6\uc2b5\ub2c8\ub2e4"}), file=sys.stderr)
            sys.exit(1)

    # Step 2: Parse remaining tokens
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--only":
            idx += 1
            if idx < len(tokens):
                opt_only = tokens[idx]
        elif tok == "--model":
            idx += 1
            if idx < len(tokens):
                opt_model = tokens[idx]
        elif tok == "--team-size":
            idx += 1
            if idx < len(tokens):
                opt_team_size = int(tokens[idx])
        elif tok == "--pool-size":
            idx += 1
            if idx < len(tokens):
                opt_pool_size = int(tokens[idx])
        elif tok == "--scale":
            idx += 1
            if idx < len(tokens):
                opt_scale = tokens[idx]
        elif tok == "--start-date":
            idx += 1
            if idx < len(tokens):
                opt_start_date = tokens[idx]
        elif tok == "--estimate-only":
            opt_estimate_only = True
        elif tok == "--workdir":
            idx += 1
            if idx < len(tokens):
                opt_workdir = tokens[idx]
        elif tok == "--leader":
            opt_leader = True
        elif tok == "--claim":
            opt_claim = True
        elif tok.startswith("TSK-"):
            tsk_id = tok
        elif tok.startswith("WP-"):
            wp_ids.append(tok)
        else:
            # Unknown token — might be manifest file path
            if os.path.isfile(tok):
                opt_workdir = tok
        idx += 1

    # Output
    result = {
        "subproject": subproject,
        "docs_dir": docs_dir,
        "tsk_id": tsk_id,
        "wp_ids": wp_ids,
        "options": {
            "only": opt_only,
            "model": opt_model,
            "team_size": opt_team_size,
            "pool_size": opt_pool_size,
            "scale": opt_scale,
            "start_date": opt_start_date,
            "estimate_only": opt_estimate_only,
            "workdir": opt_workdir,
            "leader": opt_leader,
            "claim": opt_claim,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
