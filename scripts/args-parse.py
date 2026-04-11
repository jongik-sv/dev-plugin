#!/usr/bin/env python3
"""args-parse.py — Skill argument parsing (subproject detection + option extraction).

Replaces args-parse.sh for cross-platform support.
Output format is identical JSON.

Supports two task sources:
  - wbs:  WBS Task (e.g., `TSK-01-01`) → operates on docs/wbs.md, artifacts in docs/tasks/{TSK-ID}/
  - feat: independent feature (e.g., `login-2fa`) → operates on docs/features/{name}/status.json

Source detection:
  - skill=feat → first positional (after subproject) is feature name; source="feat"
  - `feat:NAME` prefix in any skill → source="feat", id=NAME
  - `TSK-*` token → source="wbs", id=TSK-ID
"""
import sys
import os
import re
import json

USAGE = """\
Usage: args-parse.py <skill> [arguments...]

Skills: dev, dev-design, dev-build, dev-test, dev-refactor, dev-team, wbs, feat

Output: JSON with parsed arguments
  {
    "subproject": "",
    "docs_dir": "docs",
    "source": "wbs" | "feat",
    "task_id": "TSK-01-02" | "login-2fa",
    "tsk_id": "TSK-01-02",      # backward compat (wbs mode only)
    "feat_name": "",             # feat mode only
    "wp_ids": ["WP-01"],
    "options": { ... }
  }

Examples:
  args-parse.py dev "p1 TSK-01-01 --only design"
  args-parse.py dev "feat:login-2fa --only design"
  args-parse.py feat "login-2fa add 2FA to login"
  args-parse.py dev-team "p1 WP-01 WP-02 --team-size 5"
"""

FEAT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_feat_name(name: str) -> bool:
    return bool(FEAT_NAME_RE.match(name))


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
    feat_name = ""
    source = ""
    wp_ids = []
    feat_description_tokens = []
    opt_only = ""
    opt_model = ""
    opt_team_size = 3
    opt_pool_size = 5
    opt_scale = ""
    opt_start_date = ""
    opt_estimate_only = False
    opt_workdir = ""
    opt_leader = False

    tokens = args_str.split() if args_str.strip() else []
    idx = 0

    # Step 1: Subproject detection
    if tokens:
        first = tokens[0]
        if first.startswith("--"):
            pass  # option, not subproject
        elif first.startswith("WP-") or first.startswith("TSK-") or first.startswith("feat:"):
            pass  # ID, not subproject
        elif os.path.isdir(os.path.join("docs", first)):
            subproject = first
            docs_dir = f"docs/{first}"
            idx = 1
        elif first == "":
            pass
        elif skill == "feat":
            # For feat skill, first token is the feature name (not a subproject)
            pass
        else:
            print(json.dumps({"error": f"docs/{first}/ \ub514\ub809\ud1a0\ub9ac\uac00 \uc5c6\uc2b5\ub2c8\ub2e4"}), file=sys.stderr)
            sys.exit(1)

    # Step 2: Parse remaining tokens
    # For feat skill, the first non-option token (after subproject) is the feature name
    # and all subsequent non-option tokens are the description.
    feat_name_captured = False

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
                try:
                    opt_team_size = int(tokens[idx])
                except ValueError:
                    print(json.dumps({"error": f"--team-size 값이 숫자가 아닙니다: {tokens[idx]}"}))
                    sys.exit(1)
        elif tok == "--pool-size":
            idx += 1
            if idx < len(tokens):
                try:
                    opt_pool_size = int(tokens[idx])
                except ValueError:
                    print(json.dumps({"error": f"--pool-size 값이 숫자가 아닙니다: {tokens[idx]}"}))
                    sys.exit(1)
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
        elif tok.startswith("TSK-"):
            tsk_id = tok
            source = "wbs"
        elif tok.startswith("WP-"):
            wp_ids.append(tok)
        elif tok.startswith("feat:"):
            feat_name = tok[len("feat:"):]
            source = "feat"
        elif skill == "feat" and not feat_name_captured:
            # The "name slot" is now processed whether or not we capture a name
            feat_name_captured = True
            source = "feat"
            # If the first token looks like a kebab-case feature name, treat it as the name.
            # Otherwise treat it as the start of the description — the name will be
            # auto-generated later by feat-init.py.
            if FEAT_NAME_RE.match(tok):
                feat_name = tok
            else:
                feat_description_tokens.append(tok)
        elif skill == "feat" and feat_name_captured:
            # Remaining tokens form the description
            feat_description_tokens.append(tok)
        else:
            # Unknown token — might be manifest file path
            if os.path.isfile(tok):
                opt_workdir = tok
        idx += 1

    # Default source
    if not source:
        source = "wbs"

    # dev-team은 WBS 모드 전용 (Feature 모드 병렬화 미지원)
    if skill == "dev-team" and source == "feat":
        print(json.dumps({
            "error": "/dev-team은 WBS 모드 전용입니다. Feature 모드 병렬화는 지원하지 않습니다. Feature 개발은 /feat {NAME}으로 순차 실행하세요.",
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    # Post-processing for feat skill:
    # If the "name" has no hyphen AND a description follows, the user most likely
    # intended the whole thing as a description (e.g., `/feat add rate limiter`).
    # Move the captured name back into the description and let feat-init.py
    # auto-generate the name from the full string.
    # Single-token names (no description) are kept as-is so `/feat login` still works.
    if skill == "feat" and feat_name and feat_description_tokens and "-" not in feat_name:
        feat_description_tokens.insert(0, feat_name)
        feat_name = ""

    # Validate feat name if feat source
    if source == "feat" and feat_name:
        if not validate_feat_name(feat_name):
            print(json.dumps({
                "error": f"feature name 형식 오류: '{feat_name}' — kebab-case만 허용 (소문자/숫자/하이픈, 소문자로 시작)",
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

    # Unified task_id (feat_name may be empty when auto-naming is requested)
    task_id = feat_name if source == "feat" else tsk_id

    # Output
    result = {
        "subproject": subproject,
        "docs_dir": docs_dir,
        "source": source,
        "task_id": task_id,
        "tsk_id": tsk_id,
        "feat_name": feat_name,
        "feat_description": " ".join(feat_description_tokens),
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
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
