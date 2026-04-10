#!/usr/bin/env python3
"""wp-setup.py — WP worktree + prompt + tmux setup automation.

Replaces wp-setup.sh for cross-platform support.
Eliminates jq dependency — uses Python's json module.
"""
from __future__ import annotations

import sys
import os
import json
import subprocess
import shutil
import re
import tempfile
import pathlib

USAGE = "Usage: wp-setup.py <config.json>"


def run(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command."""
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True)


def detect_mux() -> str | None:
    """Detect available terminal multiplexer."""
    if shutil.which("tmux") and os.environ.get("TMUX"):
        return "tmux"
    if shutil.which("psmux"):
        return "psmux"
    return None


def extract_template(file_path: str) -> str:
    """Extract content between outer ``` markers in a template file."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find first and last ``` lines
    markers = [i for i, line in enumerate(lines) if line.strip() == "```"]
    if len(markers) < 2:
        print(f"ERROR: template ``` markers not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    first, last = markers[0], markers[-1]
    if first == last:
        print(f"ERROR: template ``` markers not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    return "".join(lines[first + 1 : last])


def substitute_vars(text: str, **kwargs) -> str:
    """Replace {VAR} placeholders in text."""
    model_override = kwargs.get("model_override", "")

    # Build --model arg for /dev skill invocation
    model_arg = f"--model {model_override}" if model_override else ""

    # Derive subproject from docs_dir (e.g. "docs/p1.5" → "p1.5", "docs" → "")
    docs_dir = kwargs.get("docs_dir", "docs")
    subproject = docs_dir.split("/", 1)[1] if "/" in docs_dir else ""

    replacements = {
        "{WP-ID}": kwargs.get("wp_id", ""),
        "{TEAM_SIZE}": str(kwargs.get("team_size", "")),
        "{WT_NAME}": kwargs.get("wt_name", ""),
        "{SHARED_SIGNAL_DIR}": kwargs.get("shared_signal_dir", ""),
        "{TEMP_DIR}": kwargs.get("temp_dir", ""),
        "{DOCS_DIR}": docs_dir,
        "{TSK-ID}": kwargs.get("tsk_id", ""),
        "{SESSION}": kwargs.get("session", ""),
        "{WORKER_MODEL}": kwargs.get("worker_model", ""),
        "{SUBPROJECT}": subproject,
        "{MODEL_ARG}": model_arg,
    }
    model_display = model_override if model_override else "\uc5c6\uc74c"
    replacements['{MODEL_OVERRIDE \ub610\ub294 "\uc5c6\uc74c"}'] = model_display

    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def insert_blocks(text: str, block1_marker: str, block1_content: str,
                  block2_marker: str = "", block2_content: str = "") -> str:
    """Replace placeholder lines with file content."""
    result = []
    for line in text.splitlines():
        if block1_marker and block1_marker in line:
            result.append(block1_content)
            continue
        if block2_marker and block2_marker in line:
            result.append(block2_content)
            continue
        result.append(line)
    return "\n".join(result)


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    config_file = sys.argv[1]

    # Check dependencies
    if not shutil.which("git"):
        print("ERROR: git required", file=sys.stderr)
        sys.exit(1)

    # Parse config
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    project_name = config.get("project_name", "")
    window_suffix = config.get("window_suffix", "")
    temp_dir = config.get("temp_dir", tempfile.gettempdir())
    shared_signal_dir = config["shared_signal_dir"]
    docs_dir = config.get("docs_dir", "docs")
    wbs_path = config["wbs_path"]
    session = config.get("session", "")
    model_override = config.get("model_override", "")
    worker_model = config.get("worker_model", "sonnet")
    wp_leader_model = config.get("wp_leader_model", "sonnet")
    plugin_root = config["plugin_root"]

    ddtr_template_path = os.path.join(plugin_root, "skills/dev-team/references/ddtr-prompt-template.md")
    wp_leader_template_path = os.path.join(plugin_root, "skills/dev-team/references/wp-leader-prompt.md")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wbs_parse = os.path.join(script_dir, "wbs-parse.py")

    # Template caching
    ddtr_raw = extract_template(ddtr_template_path)
    wp_leader_raw = extract_template(wp_leader_template_path)

    ddtr_prefix = ""
    if model_override:
        ddtr_prefix = f'\u26a0\ufe0f MODEL_OVERRIDE = "{model_override}" \u2014 \uc544\ub798 \ubaa8\ub4e0 Phase\uc758 model \ud30c\ub77c\ubbf8\ud130\uc5d0 \uc774 \uac12\uc744 \uc0ac\uc6a9\ud558\ub77c.\n\n'

    sub_kwargs = dict(
        shared_signal_dir=shared_signal_dir,
        temp_dir=temp_dir,
        docs_dir=docs_dir,
        session=session,
        worker_model=worker_model,
        model_override=model_override,
    )

    mux = detect_mux()
    wps = config.get("wps", [])

    for wp_cfg in wps:
        wp_id = wp_cfg["wp_id"]
        team_size = wp_cfg.get("team_size", 3)
        execution_plan = wp_cfg.get("execution_plan", "")
        tasks = wp_cfg.get("tasks", [])

        wt_name = f"{wp_id}{window_suffix}"

        print(f"=== [{wp_id}] setup start ===")

        # --- 1. Worktree ---
        wt_path = f".claude/worktrees/{wt_name}"
        resume_mode = False

        branch_check = run(f"git branch --list dev/{wt_name}", capture=True, check=False)
        if os.path.isdir(wt_path) and branch_check.stdout.strip():
            print(f"[{wp_id}] worktree: resume ({wt_path})")
            resume_mode = True
        else:
            run(f'git worktree add "{wt_path}" -b "dev/{wt_name}"')
            print(f"[{wp_id}] worktree: created ({wt_path})")

        # --- 2. Signal dir + restore ---
        os.makedirs(shared_signal_dir, exist_ok=True)

        if resume_mode:
            # Restore signals from completed tasks in worktrees
            import glob
            for wt_dir in glob.glob(".claude/worktrees/*/"):
                wt_wbs = os.path.join(wt_dir, docs_dir, "wbs.md")
                if not os.path.isfile(wt_wbs):
                    continue
                with open(wt_wbs, "r", encoding="utf-8") as f:
                    wt_wbs_text = f.read()
                for m in re.finditer(r'TSK-\d+(?:-\d+)+', wt_wbs_text):
                    tsk = m.group()
                    done_path = os.path.join(shared_signal_dir, f"{tsk}.done")
                    if not os.path.exists(done_path):
                        # Check if [xx] in the line containing this TSK
                        for line in wt_wbs_text.splitlines():
                            if tsk in line and "[xx]" in line:
                                pathlib.Path(done_path).write_text("resumed\n", encoding="utf-8")
                                break

            # Remove stale .running files
            for f in pathlib.Path(shared_signal_dir).glob("*.running"):
                f.unlink()
            init_file = os.path.join(shared_signal_dir, f"{wt_name}.initialized")
            if os.path.exists(init_file):
                os.unlink(init_file)
            print(f"[{wp_id}] signals: restore complete ({shared_signal_dir})")

        # --- 3. DDTR prompt generation + data collection ---
        ddtr_files = []
        manifest_tasks = ""
        all_task_blocks = ""

        for tsk_id in tasks:
            # Get task status via wbs-parse.py
            r = run(f'python3 "{wbs_parse}" "{wbs_path}" "{tsk_id}" --field status', capture=True, check=False)
            status = r.stdout.strip()
            if "[xx]" in status:
                continue

            r = run(f'python3 "{wbs_parse}" "{wbs_path}" "{tsk_id}" --field depends', capture=True, check=False)
            depends = r.stdout.strip() or "(none)"

            r = run(f'python3 "{wbs_parse}" "{wbs_path}" "{tsk_id}" --block', capture=True, check=False)
            task_block = r.stdout

            all_task_blocks += task_block + "\n\n"

            # DDTR prompt generation (reuse if exists)
            ddtr_out = os.path.join(temp_dir, f"task-{tsk_id}.txt")
            if os.path.isfile(ddtr_out):
                print(f"[{wp_id}] ddtr: {tsk_id} reuse ({ddtr_out})")
            else:
                content = ddtr_prefix + ddtr_raw
                content = substitute_vars(content, wp_id=wp_id, team_size=team_size,
                                          wt_name=wt_name, tsk_id=tsk_id, **sub_kwargs)

                tmp_out = ddtr_out + ".tmp"
                with open(tmp_out, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_out, ddtr_out)

            ddtr_files.append(tsk_id)
            manifest_tasks += f"""
### {tsk_id}
- status: {status}
- depends: {depends}
- prompt_file: {temp_dir}/task-{tsk_id}.txt
"""

        print(f"[{wp_id}] ddtr: {' '.join(ddtr_files) if ddtr_files else 'none'}")

        # All tasks [xx] — skip
        if not ddtr_files:
            print(f"[{wp_id}] all tasks [xx] — skip")
            done_path = os.path.join(shared_signal_dir, f"{wt_name}.done")
            pathlib.Path(done_path).write_text("all tasks already [xx]\n", encoding="utf-8")
            continue

        # --- 4. Manifest ---
        manifest_path = os.path.join(temp_dir, f"team-manifest-{wt_name}.md")
        manifest_content = f"""# Configuration
- team_size: {team_size}
- window_name: {wt_name}
- signal_dir: {shared_signal_dir}
- docs_dir: {docs_dir}
- worker_model: {worker_model}

## Tasks
{manifest_tasks}"""
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_content)
        print(f"[{wp_id}] manifest: {manifest_path}")

        # --- 5. WP leader prompt ---
        wp_leader_out = f".claude/worktrees/{wt_name}-prompt.txt"
        if os.path.isfile(wp_leader_out):
            print(f"[{wp_id}] leader: reuse ({wp_leader_out})")
        else:
            content = wp_leader_raw
            content = substitute_vars(content, wp_id=wp_id, team_size=team_size,
                                      wt_name=wt_name, tsk_id="", **sub_kwargs)
            content = insert_blocks(
                content,
                "[WP \ub0b4 \ubaa8\ub4e0 Task \ube14\ub85d", all_task_blocks,
                "[\ud300\ub9ac\ub354\uac00 \uc0b0\ucd9c\ud55c \ub808\ubca8\ubcc4 \uc2e4\ud589 \uacc4\ud68d]", execution_plan,
            )
            tmp_out = wp_leader_out + ".tmp"
            with open(tmp_out, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_out, wp_leader_out)
            print(f"[{wp_id}] leader: {wp_leader_out}")

        # --- 6. Runner + tmux/psmux spawn ---
        runner_path = f".claude/worktrees/{wt_name}-run.sh"
        runner_content = f"""#!/bin/bash
cd "$(dirname "$0")/{wt_name}"
exec claude --dangerously-skip-permissions --model {wp_leader_model} "$(<../{wt_name}-prompt.txt)"
"""
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(runner_content)
        os.chmod(runner_path, 0o755)

        if mux == "tmux" and session:
            run(f'tmux new-window -t "{session}:" -n "{wt_name}" "{runner_path}"')
            # Get the window index for the newly created window (dot in name breaks tmux target)
            r = run(f"tmux list-windows -t \"{session}\" -F '#{{window_index}}:#{{window_name}}' | grep ':{wt_name}$'",
                    capture=True, check=False)
            win_idx = r.stdout.strip().split(":")[0] if r.stdout.strip() else ""
            win_target = f"{session}:{win_idx}" if win_idx else f"{session}:{wt_name}"
            run(f'tmux set-option -w -t "{win_target}" automatic-rename off')
            run(f'tmux set-option -w -t "{win_target}" allow-rename off')
            run(f'tmux set-option -w -t "{win_target}" pane-border-status top')
            run(f'tmux set-option -w -t "{win_target}" pane-border-format " #{{pane_title}} "')

            wt_abs_path = os.path.join(os.getcwd(), f".claude/worktrees/{wt_name}")
            for wi in range(1, team_size + 1):
                run(f"tmux split-window -t \"{win_target}\" -h "
                    f"\"cd '{wt_abs_path}' && claude --dangerously-skip-permissions --model {worker_model}\"")
            run(f'tmux select-layout -t "{win_target}" tiled')

            # Pane ID file
            pane_ids_file = os.path.join(temp_dir, f"pane-ids-{wt_name}.txt")
            run(f"tmux list-panes -t \"{win_target}\" -F '#{{pane_index}}:#{{pane_id}}' > \"{pane_ids_file}\"")

            # Read pane IDs and set titles
            with open(pane_ids_file, "r", encoding="utf-8") as f:
                pane_lines = f.read().strip().splitlines()

            pane_map = {}
            for line in pane_lines:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    pane_map[parts[0]] = parts[1]

            if "0" in pane_map:
                run(f'tmux select-pane -t "{pane_map["0"]}" -T "{wp_id} Leader"')
            for wi in range(1, team_size + 1):
                idx = str(wi)
                if idx in pane_map:
                    run(f'tmux select-pane -t "{pane_map[idx]}" -T "worker{wi} idle"')

            print(f"[{wp_id}] spawn: tmux window {wt_name} (leader + {team_size} workers)")

        elif mux == "psmux" and session:
            # psmux support — similar commands, may need adjustment
            run(f'psmux new-window -t "{session}:" -n "{wt_name}" "{runner_path}"', check=False)
            print(f"[{wp_id}] spawn: psmux window {wt_name}")

        else:
            print(f"[{wp_id}] runner: {runner_path} (no tmux — manual execution required)")

        print(f"=== [{wp_id}] setup complete ===")

    print()
    print(f"Total setup complete: {len(wps)} WPs")
    print(f"Signal directory: {shared_signal_dir}")


if __name__ == "__main__":
    main()
