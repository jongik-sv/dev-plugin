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

# Import cross-platform path normalizer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _platform import normalize_path

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


def py_wbs(wbs_parse: str, *args: str) -> str:
    """Invoke wbs-parse.py via sys.executable. Fail loud on rc != 0.

    Why: hardcoded "python3" is intercepted by the Windows App Execution Alias
    (Microsoft Store stub), which exits rc=9009 with empty stdout. With check=False
    that silently corrupts [xx]/[ ]/[dd] status filtering downstream — completed
    tasks get re-queued and design.done files get pre-created for untouched tasks.
    """
    r = subprocess.run([sys.executable, wbs_parse, *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: wbs-parse failed ({' '.join(args)}): rc={r.returncode}",
              file=sys.stderr)
        if r.stderr.strip():
            print(f"  stderr: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return r.stdout


def detect_mux() -> tuple[str | None, str | None]:
    """Detect available multiplexer. Returns (kind, binary_path).

    kind ∈ {'tmux', 'psmux', None}. On Windows, psmux registers itself as both
    'tmux' and 'psmux' aliases pointing to the same binary — disambiguate by
    probing `tmux -V` output for the 'psmux' substring.
    """
    tmux_bin = shutil.which("tmux")
    if tmux_bin and os.environ.get("TMUX"):
        try:
            r = subprocess.run([tmux_bin, "-V"], capture_output=True, text=True, timeout=5)
            probe = (r.stdout or "") + (r.stderr or "")
            if "psmux" in probe.lower():
                return ("psmux", tmux_bin)
            return ("tmux", tmux_bin)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    psmux_bin = shutil.which("psmux")
    if psmux_bin:
        return ("psmux", psmux_bin)
    return (None, None)


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
        "{PYTHON_BIN}": sys.executable,
        "{INIT_FILE}": kwargs.get("init_file", ""),
        "{CLEANUP_FILE}": kwargs.get("cleanup_file", ""),
        "{ON_FAIL}": kwargs.get("on_fail", "bypass"),
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

    # Require a git repository — worktree operations fail silently otherwise,
    # leaving partially-created signal state that confuses the next resume.
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        print("ERROR: not inside a git repository. /dev-team requires a git repo "
              "for worktree-per-WP isolation.", file=sys.stderr)
        print("  Fix: run `git init && git add -A && git commit -m \"initial\"` "
              "in the project root first.", file=sys.stderr)
        sys.exit(1)

    # Parse config
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    project_name = config.get("project_name", "")
    window_suffix = config.get("window_suffix", "").replace(".", "_")  # dot breaks tmux target syntax (session:window.pane)
    temp_dir = normalize_path(config.get("temp_dir", tempfile.gettempdir()))
    shared_signal_dir = normalize_path(config["shared_signal_dir"])
    docs_dir = config.get("docs_dir", "docs")
    wbs_path = normalize_path(config["wbs_path"])
    session = config.get("session", "")
    model_override = config.get("model_override", "")
    worker_model = config.get("worker_model", "sonnet")
    wp_leader_model = config.get("wp_leader_model", "sonnet")
    plugin_root = normalize_path(config["plugin_root"])
    on_fail = config.get("on_fail", "bypass")

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
        on_fail=on_fail,
    )

    mux, mux_bin = detect_mux()
    is_windows = sys.platform == "win32"
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
            depends_str = py_wbs(wbs_parse, wbs_path, tsk_id, "--field", "depends").strip()
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
                dep_status = py_wbs(wbs_parse, wbs_path, dep, "--field", "status")
                if "[xx]" in dep_status:
                    pathlib.Path(done_path).write_text(
                        "pre-created: completed in main WBS\n", encoding="utf-8")

        # --- 3. DDTR prompt generation + data collection ---
        ddtr_files = []
        manifest_tasks = ""
        all_task_blocks = ""

        for tsk_id in tasks:
            status = py_wbs(wbs_parse, wbs_path, tsk_id, "--field", "status").strip()
            if "[xx]" in status:
                continue

            depends = py_wbs(wbs_parse, wbs_path, tsk_id, "--field", "depends").strip() or "(none)"
            task_block = py_wbs(wbs_parse, wbs_path, tsk_id, "--block")

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
                with open(tmp_out, "w", encoding="utf-8", newline="\n") as f:
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
                    with open(tmp_out, "w", encoding="utf-8", newline="\n") as f:
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
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
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
        # Always regenerate — settings like on_fail may change between runs
        content = wp_leader_raw
        content = substitute_vars(content, **var_kwargs)
        content = insert_blocks(
            content,
            "[WP \ub0b4 \ubaa8\ub4e0 Task \ube14\ub85d", all_task_blocks,
            "[\ud300\ub9ac\ub354\uac00 \uc0b0\ucd9c\ud55c \ub808\ubca8\ubcc4 \uc2e4\ud589 \uacc4\ud68d]", execution_plan,
        )
        tmp_out = wp_leader_out + ".tmp"
        with open(tmp_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_out, wp_leader_out)
        print(f"[{wp_id}] leader: {wp_leader_out}")

        # Init file (read once at startup) — always regenerate
        wp_init_out = f".claude/worktrees/{wt_name}-init.txt"
        init_content = substitute_vars(wp_leader_init_raw, **var_kwargs)
        tmp_out = wp_init_out + ".tmp"
        with open(tmp_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(init_content)
        os.replace(tmp_out, wp_init_out)
        print(f"[{wp_id}] leader-init: {wp_init_out}")

        # Cleanup file (read at end) — always regenerate
        wp_cleanup_out = f".claude/worktrees/{wt_name}-cleanup.txt"
        cleanup_content = substitute_vars(wp_leader_cleanup_raw, **var_kwargs)
        tmp_out = wp_cleanup_out + ".tmp"
        with open(tmp_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(cleanup_content)
        os.replace(tmp_out, wp_cleanup_out)
        print(f"[{wp_id}] leader-cleanup: {wp_cleanup_out}")

        # --- 6. tmux/psmux spawn (team-mode compatible) ---
        # Use the same spawn pattern as team-mode: pass a shell command string
        # to new-window / split-window.  This works on both native tmux and
        # psmux (Windows) because psmux executes the command in its default
        # shell context — Python runner scripts fail under psmux because it
        # opens PowerShell/WSL where Windows Python paths are invalid.
        #
        # Leader receives its initial prompt via send-keys after spawn, the
        # same way team-mode dispatches tasks to workers.
        worktree_abs = os.path.abspath(wt_path)
        leader_model_flag = f" --model {wp_leader_model}" if wp_leader_model else ""
        worker_model_flag = f" --model {worker_model}" if worker_model else ""
        leader_prompt_abs = os.path.abspath(wp_leader_out)

        if mux == "psmux":
            # psmux opens PowerShell by default — use semicolon and
            # PowerShell-compatible Set-Location instead of bash &&
            leader_spawn = f'Set-Location "{worktree_abs}"; claude --dangerously-skip-permissions{leader_model_flag}'
            worker_spawn = f'Set-Location "{worktree_abs}"; claude --dangerously-skip-permissions{worker_model_flag}'
        else:
            leader_spawn = f'cd "{worktree_abs}" && claude --dangerously-skip-permissions{leader_model_flag}'
            worker_spawn = f'cd "{worktree_abs}" && claude --dangerously-skip-permissions{worker_model_flag}'

        if mux and mux_bin and session:
            run_cmd([mux_bin, "new-window", "-t", f"{session}:", "-n", wt_name, leader_spawn])
            # Get the window index for the newly created window (dot in name breaks tmux target)
            r = run_cmd([mux_bin, "list-windows", "-t", session,
                         "-F", "#{window_index}:#{window_name}"],
                        capture=True, check=False)
            win_idx = ""
            for wline in r.stdout.strip().splitlines():
                if wline.endswith(f":{wt_name}"):
                    win_idx = wline.split(":")[0]
                    break
            win_target = f"{session}:{win_idx}" if win_idx else f"{session}:{wt_name}"

            # psmux may not implement every tmux option; treat visual tweaks as
            # best-effort so a missing option doesn't abort the whole spawn.
            opt_check = (mux == "tmux")
            run_cmd([mux_bin, "set-option", "-w", "-t", win_target, "automatic-rename", "off"], check=opt_check)
            run_cmd([mux_bin, "set-option", "-w", "-t", win_target, "allow-rename", "off"], check=opt_check)
            run_cmd([mux_bin, "set-option", "-w", "-t", win_target, "pane-border-status", "top"], check=opt_check)
            # Unified label format with team-mode: @label + pane_index
            run_cmd([mux_bin, "set-option", "-w", "-t", win_target,
                     "pane-border-format", " #{pane_index}: #{@label} "], check=opt_check)

            for wi in range(1, team_size + 1):
                run_cmd([mux_bin, "split-window", "-t", win_target, "-h", worker_spawn])
            run_cmd([mux_bin, "select-layout", "-t", win_target, "tiled"])

            # Pane ID collection
            pane_ids_file = os.path.join(temp_dir, f"pane-ids-{wt_name}.txt")
            r = run_cmd([mux_bin, "list-panes", "-t", win_target,
                         "-F", "#{pane_index}:#{pane_id}"],
                        capture=True, check=False)
            with open(pane_ids_file, "w", encoding="utf-8", newline="\n") as f:
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
                run_cmd([mux_bin, "set-option", "-p", "-t", pane_map["0"], "@label", f"{wp_id} Leader"], check=opt_check)
            for wi in range(1, team_size + 1):
                idx = str(wi)
                if idx in pane_map:
                    run_cmd([mux_bin, "set-option", "-p", "-t", pane_map[idx], "@label", f"팀원{wi} 대기"], check=opt_check)

            # Send initial prompt to leader pane via send-prompt.py helper.
            # The helper handles the Windows/psmux bracketed-paste quirk that
            # swallows a trailing Enter when text + Enter are passed to
            # send-keys in a single call. On macOS/Linux the helper keeps the
            # original one-call behavior.
            if "0" in pane_map:
                leader_pane_id = pane_map["0"]
                time.sleep(3)
                run_cmd([mux_bin, "send-keys", "-t", leader_pane_id, "Escape"], check=False)
                time.sleep(1)
                send_prompt = os.path.join(plugin_root, "scripts", "send-prompt.py")
                run_cmd([sys.executable, send_prompt, leader_pane_id,
                         "--text",
                         f"{leader_prompt_abs} 파일을 Read 도구로 읽고 그 안의 지시를 따르라."],
                        check=False)

            print(f"[{wp_id}] spawn: {mux} window {wt_name} (leader + {team_size} workers)")

        else:
            print(f"[{wp_id}] runner: manual execution required (no tmux)")

        print(f"=== [{wp_id}] setup complete ===")

    print()
    print(f"Total setup complete: {len(wps)} WPs")
    print(f"Signal directory: {shared_signal_dir}")


if __name__ == "__main__":
    main()
