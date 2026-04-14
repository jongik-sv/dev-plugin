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
import time
import pathlib
import glob

# Resume protocol: .running files older than this are considered stale
# (heartbeat interval is 2 min per signal-protocol.md; 5 min = 2.5x grace)
STALE_RUNNING_SECONDS = 300

USAGE = "Usage: wp-setup.py <config.json>"

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9._-]+$')


def _validate_name(value: str, label: str) -> str:
    """Validate that a name contains only safe characters."""
    if not _SAFE_NAME_RE.match(value):
        print(f"ERROR: {label} contains unsafe characters: {value!r}", file=sys.stderr)
        sys.exit(1)
    return value


def run_cmd(args: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command as argument list (no shell)."""
    return subprocess.run(args, check=check, capture_output=capture, text=True)


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
        "{PLUGIN_ROOT}": kwargs.get("plugin_root", ""),
        "{INIT_FILE}": kwargs.get("init_file", ""),
        "{CLEANUP_FILE}": kwargs.get("cleanup_file", ""),
    }
    model_display = model_override if model_override else "\uc5c6\uc74c"
    replacements['{MODEL_OVERRIDE}'] = model_display

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
    window_suffix = config.get("window_suffix", "").replace(".", "_")  # dot breaks tmux target syntax (session:window.pane)
    temp_dir = config.get("temp_dir", tempfile.gettempdir())
    shared_signal_dir = config["shared_signal_dir"]
    docs_dir = config.get("docs_dir", "docs")
    wbs_path = config["wbs_path"]
    session = config.get("session", "")
    model_override = config.get("model_override", "")
    worker_model = config.get("worker_model", "sonnet")
    wp_leader_model = config.get("wp_leader_model", "sonnet")
    plugin_root = config["plugin_root"]

    # Validate model names
    if model_override:
        _validate_name(model_override, "model_override")
    _validate_name(worker_model, "worker_model")
    _validate_name(wp_leader_model, "wp_leader_model")

    ddtr_template_path = os.path.join(plugin_root, "skills/dev-team/references/ddtr-prompt-template.md")
    ddtr_design_template_path = os.path.join(plugin_root, "skills/dev-team/references/ddtr-design-template.md")
    wp_leader_template_path = os.path.join(plugin_root, "skills/dev-team/references/wp-leader-prompt.md")
    wp_leader_init_path = os.path.join(plugin_root, "skills/dev-team/references/wp-leader-init.md")
    wp_leader_cleanup_path = os.path.join(plugin_root, "skills/dev-team/references/wp-leader-cleanup.md")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wbs_parse = os.path.join(script_dir, "wbs-parse.py")

    # Template caching
    ddtr_raw = extract_template(ddtr_template_path)
    ddtr_design_raw = extract_template(ddtr_design_template_path)
    wp_leader_raw = extract_template(wp_leader_template_path)
    wp_leader_init_raw = extract_template(wp_leader_init_path)
    wp_leader_cleanup_raw = extract_template(wp_leader_cleanup_path)

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
        plugin_root=plugin_root,
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

        branch_check = run_cmd(["git", "branch", "--list", f"dev/{wt_name}"], capture=True, check=False)
        if os.path.isdir(wt_path) and branch_check.stdout.strip():
            # Health check: verify worktree is in a usable state
            health = run_cmd(["git", "-C", wt_path, "status", "--porcelain"], capture=True, check=False)
            if health.returncode != 0:
                print(f"[{wp_id}] worktree: unhealthy, recreating ({wt_path})")
                run_cmd(["git", "worktree", "remove", "--force", wt_path], check=False)
                run_cmd(["git", "branch", "-D", f"dev/{wt_name}"], check=False)
                run_cmd(["git", "worktree", "add", wt_path, "-b", f"dev/{wt_name}"])
            else:
                print(f"[{wp_id}] worktree: resume ({wt_path})")
                resume_mode = True
        else:
            run_cmd(["git", "worktree", "add", wt_path, "-b", f"dev/{wt_name}"])
            print(f"[{wp_id}] worktree: created ({wt_path})")

        # --- 2. Signal dir + restore ---
        os.makedirs(shared_signal_dir, exist_ok=True)

        if resume_mode:
            # Restore signals from completed tasks in worktrees
            for wt_dir in glob.glob(".claude/worktrees/*/"):
                wt_wbs = os.path.join(wt_dir, docs_dir, "wbs.md")
                if not os.path.isfile(wt_wbs):
                    continue
                with open(wt_wbs, "r", encoding="utf-8") as f:
                    wt_wbs_text = f.read()
                for m in re.finditer(r'TSK-\d+(?:-\d+)+', wt_wbs_text):
                    tsk = m.group()
                    done_path = os.path.join(shared_signal_dir, f"{tsk}.done")
                    design_done_path = os.path.join(shared_signal_dir, f"{tsk}-design.done")
                    for line in wt_wbs_text.splitlines():
                        if tsk not in line:
                            continue
                        # [xx] → restore both .done and -design.done
                        if "[xx]" in line:
                            if not os.path.exists(done_path):
                                pathlib.Path(done_path).write_text("resumed\n", encoding="utf-8")
                            if not os.path.exists(design_done_path):
                                pathlib.Path(design_done_path).write_text("resumed\n", encoding="utf-8")
                            break
                        # [dd] or [im] → design already done, restore -design.done
                        if ("[dd]" in line or "[im]" in line) and not os.path.exists(design_done_path):
                            pathlib.Path(design_done_path).write_text("resumed\n", encoding="utf-8")
                            break

            # Resume protocol (references/signal-protocol.md):
            #   .done     → 유지 (완료 증거, 리더가 스킵)
            #   .failed   → 삭제 (재실행 허용)
            #   .shutdown → 삭제 (사용자 중단 마커, state.json 기반 정상 재개)
            #   .running  → stale 감지 후 제거 (mtime > STALE_RUNNING_SECONDS)
            now = time.time()
            removed_failed = 0
            removed_shutdown = 0
            removed_running = 0
            kept_running = 0
            for f in pathlib.Path(shared_signal_dir).glob("*.failed"):
                f.unlink()
                removed_failed += 1
            for f in pathlib.Path(shared_signal_dir).glob("*.shutdown"):
                f.unlink()
                removed_shutdown += 1
            for f in pathlib.Path(shared_signal_dir).glob("*.running"):
                try:
                    age = now - f.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age >= STALE_RUNNING_SECONDS:
                    f.unlink()
                    removed_running += 1
                else:
                    kept_running += 1
            init_file = os.path.join(shared_signal_dir, f"{wt_name}.initialized")
            if os.path.exists(init_file):
                os.unlink(init_file)
            print(
                f"[{wp_id}] signals: restore complete "
                f"(failed-removed={removed_failed}, "
                f"shutdown-removed={removed_shutdown}, "
                f"running-stale-removed={removed_running}, "
                f"running-live-kept={kept_running}) "
                f"({shared_signal_dir})"
            )

        # --- 2b. Pre-create .done for completed cross-WP dependencies ---
        # Even if worktrees were removed, the main WBS has [xx] status.
        for tsk_id in tasks:
            r = run_cmd(["python3", wbs_parse, wbs_path, tsk_id, "--field", "depends"],
                        capture=True, check=False)
            depends_str = r.stdout.strip()
            if not depends_str or depends_str == "-":
                continue
            wp_num = wp_id.split("-")[1] if len(wp_id.split("-")) >= 2 else ""
            for dep in re.split(r'[,\s]+', depends_str):
                dep = dep.strip()
                if not dep.startswith("TSK-"):
                    continue
                dep_wp_num = dep.split("-")[1] if len(dep.split("-")) >= 2 else ""
                if dep_wp_num == wp_num:
                    continue  # intra-WP — handled by WP leader
                done_path = os.path.join(shared_signal_dir, f"{dep}.done")
                if os.path.exists(done_path):
                    continue
                r2 = run_cmd(["python3", wbs_parse, wbs_path, dep, "--field", "status"],
                             capture=True, check=False)
                if "[xx]" in r2.stdout:
                    pathlib.Path(done_path).write_text(
                        "pre-created: completed in main WBS\n", encoding="utf-8")

        # --- 3. DDTR prompt generation + data collection ---
        ddtr_files = []
        manifest_tasks = ""
        all_task_blocks = ""

        for tsk_id in tasks:
            # Get task status via wbs-parse.py
            r = run_cmd(["python3", wbs_parse, wbs_path, tsk_id, "--field", "status"],
                        capture=True, check=False)
            status = r.stdout.strip()
            if "[xx]" in status:
                continue

            r = run_cmd(["python3", wbs_parse, wbs_path, tsk_id, "--field", "depends"],
                        capture=True, check=False)
            depends = r.stdout.strip() or "(none)"

            r = run_cmd(["python3", wbs_parse, wbs_path, tsk_id, "--block"],
                        capture=True, check=False)
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

            # Design-only prompt generation for design-ahead
            design_done_path = os.path.join(shared_signal_dir, f"{tsk_id}-design.done")
            if "[ ]" in status:
                # Task not yet designed — generate design prompt
                design_out = os.path.join(temp_dir, f"task-{tsk_id}-design.txt")
                if os.path.isfile(design_out):
                    print(f"[{wp_id}] design: {tsk_id} reuse ({design_out})")
                else:
                    content = ddtr_prefix + ddtr_design_raw
                    content = substitute_vars(content, wp_id=wp_id, team_size=team_size,
                                              wt_name=wt_name, tsk_id=tsk_id, **sub_kwargs)
                    tmp_out = design_out + ".tmp"
                    with open(tmp_out, "w", encoding="utf-8") as f:
                        f.write(content)
                    os.replace(tmp_out, design_out)
            else:
                # [dd] or [im] — design already done, pre-create signal
                if not os.path.exists(design_done_path):
                    pathlib.Path(design_done_path).write_text(
                        "pre-created: design already done\n", encoding="utf-8")

            ddtr_files.append(tsk_id)
            design_prompt_line = f"- design_prompt: {temp_dir}/task-{tsk_id}-design.txt\n" if "[ ]" in status else ""
            manifest_tasks += f"""
### {tsk_id}
- status: {status}
- depends: {depends}
{design_prompt_line}- prompt_file: {temp_dir}/task-{tsk_id}.txt
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

        # --- 5. WP leader prompt (core + init + cleanup) ---
        init_file_abs = os.path.abspath(f".claude/worktrees/{wt_name}-init.txt")
        cleanup_file_abs = os.path.abspath(f".claude/worktrees/{wt_name}-cleanup.txt")
        var_kwargs = dict(wp_id=wp_id, team_size=team_size,
                          wt_name=wt_name, tsk_id="",
                          init_file=init_file_abs, cleanup_file=cleanup_file_abs,
                          **sub_kwargs)

        wp_leader_out = f".claude/worktrees/{wt_name}-prompt.txt"
        if os.path.isfile(wp_leader_out):
            print(f"[{wp_id}] leader: reuse ({wp_leader_out})")
        else:
            content = wp_leader_raw
            content = substitute_vars(content, **var_kwargs)
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

        # Init file (read once at startup)
        wp_init_out = f".claude/worktrees/{wt_name}-init.txt"
        if not os.path.isfile(wp_init_out):
            init_content = substitute_vars(wp_leader_init_raw, **var_kwargs)
            tmp_out = wp_init_out + ".tmp"
            with open(tmp_out, "w", encoding="utf-8") as f:
                f.write(init_content)
            os.replace(tmp_out, wp_init_out)
            print(f"[{wp_id}] leader-init: {wp_init_out}")

        # Cleanup file (read at end)
        wp_cleanup_out = f".claude/worktrees/{wt_name}-cleanup.txt"
        if not os.path.isfile(wp_cleanup_out):
            cleanup_content = substitute_vars(wp_leader_cleanup_raw, **var_kwargs)
            tmp_out = wp_cleanup_out + ".tmp"
            with open(tmp_out, "w", encoding="utf-8") as f:
                f.write(cleanup_content)
            os.replace(tmp_out, wp_cleanup_out)
            print(f"[{wp_id}] leader-cleanup: {wp_cleanup_out}")

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
            run_cmd(["tmux", "new-window", "-t", f"{session}:", "-n", wt_name, runner_path])
            # Get the window index for the newly created window (dot in name breaks tmux target)
            r = run_cmd(["tmux", "list-windows", "-t", session,
                         "-F", "#{window_index}:#{window_name}"],
                        capture=True, check=False)
            win_idx = ""
            for wline in r.stdout.strip().splitlines():
                if wline.endswith(f":{wt_name}"):
                    win_idx = wline.split(":")[0]
                    break
            win_target = f"{session}:{win_idx}" if win_idx else f"{session}:{wt_name}"
            run_cmd(["tmux", "set-option", "-w", "-t", win_target, "automatic-rename", "off"])
            run_cmd(["tmux", "set-option", "-w", "-t", win_target, "allow-rename", "off"])
            run_cmd(["tmux", "set-option", "-w", "-t", win_target, "pane-border-status", "top"])
            # Unified label format with team-mode: @label + pane_index
            run_cmd(["tmux", "set-option", "-w", "-t", win_target,
                     "pane-border-format", " #{pane_index}: #{@label} "])

            wt_abs_path = os.path.join(os.getcwd(), f".claude/worktrees/{wt_name}")
            for wi in range(1, team_size + 1):
                run_cmd(["tmux", "split-window", "-t", win_target, "-h",
                         f"cd '{wt_abs_path}' && claude --dangerously-skip-permissions --model {worker_model}"])
            run_cmd(["tmux", "select-layout", "-t", win_target, "tiled"])

            # Pane ID collection
            pane_ids_file = os.path.join(temp_dir, f"pane-ids-{wt_name}.txt")
            r = run_cmd(["tmux", "list-panes", "-t", win_target,
                         "-F", "#{pane_index}:#{pane_id}"],
                        capture=True, check=False)
            with open(pane_ids_file, "w", encoding="utf-8") as f:
                f.write(r.stdout)

            # Read pane IDs and set titles
            pane_lines = r.stdout.strip().splitlines()

            pane_map = {}
            for line in pane_lines:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    pane_map[parts[0]] = parts[1]

            # Initial labels via @label (unified with team-mode). Runtime updates
            # from WP leader also use `tmux set-option -p -t {paneId} @label "..."`.
            if "0" in pane_map:
                run_cmd(["tmux", "set-option", "-p", "-t", pane_map["0"], "@label", f"{wp_id} Leader"])
            for wi in range(1, team_size + 1):
                idx = str(wi)
                if idx in pane_map:
                    run_cmd(["tmux", "set-option", "-p", "-t", pane_map[idx], "@label", f"팀원{wi} 대기"])

            print(f"[{wp_id}] spawn: tmux window {wt_name} (leader + {team_size} workers)")

        elif mux == "psmux" and session:
            # psmux support — similar commands, may need adjustment
            run_cmd(["psmux", "new-window", "-t", f"{session}:", "-n", wt_name, runner_path], check=False)
            print(f"[{wp_id}] spawn: psmux window {wt_name}")

        else:
            print(f"[{wp_id}] runner: {runner_path} (no tmux — manual execution required)")

        print(f"=== [{wp_id}] setup complete ===")

    print()
    print(f"Total setup complete: {len(wps)} WPs")
    print(f"Signal directory: {shared_signal_dir}")


if __name__ == "__main__":
    main()
