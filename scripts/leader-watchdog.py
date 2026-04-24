#!/usr/bin/env python3
"""leader-watchdog.py — Zero-LLM daemon that monitors one WP leader pane.

Responsibilities on detected leader death:
  1. Dump autopsy (delegates to leader-autopsy.py — best effort).
  2. Wait for the WP's workers to settle:
     - per-task .done/.failed/.bypassed present, OR
     - .running heartbeat older than HEARTBEAT_GRACE_SEC (stale worker).
  3. Atomically write {WT_NAME}.needs-restart JSON signal.
  4. Exit.

The team leader's signal-helper.py wait loop picks up .needs-restart
and drives restart via wp-setup.py resume mode.

Token cost is ZERO during polling — only the small .needs-restart payload
(~1 KB) reaches the team leader's LLM context on the single death event.

stdlib only, no pip dependencies.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _platform import normalize_path  # noqa: E402

HEARTBEAT_GRACE_SEC = 300
DEFAULT_POLL_INTERVAL = 30
DEFAULT_CONFIRM_STREAK = 2
DEFAULT_WORKER_SETTLE_TIMEOUT = 7200
DEFAULT_AUTOPSY_TIMEOUT = 180


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(log_path: pathlib.Path, msg: str) -> None:
    try:
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{_now_iso()}] {msg}\n")
    except OSError:
        pass


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1, "", ""


def pane_dead(session: str, wt_name: str) -> bool:
    target = f"{session}:{wt_name}.0"
    rc, out, _ = _run(["tmux", "display-message", "-t", target, "-p", "#{pane_dead}"])
    if rc != 0:
        return False
    return out.strip() == "1"


def window_exists(session: str, wt_name: str) -> bool:
    rc, out, _ = _run(["tmux", "list-windows", "-t", session, "-F", "#{window_name}"])
    if rc != 0:
        return False
    return wt_name in out.splitlines()


def check_window_and_pane(session: str, wt_name: str) -> "tuple[bool, bool]":
    """Check window existence and pane liveness in a single tmux call.

    Replaces the previous ``window_exists()`` + ``pane_dead()`` two-call pattern
    with a single ``list-windows -F "#{window_name}\t#{pane_dead}"`` invocation,
    reducing tmux subprocess forks from 2 to 1 per poll cycle.

    Args:
        session: tmux session name.
        wt_name: worktree window name to look up.

    Returns:
        ``(window_exists, pane_is_dead)`` — both False when tmux is unavailable
        or the command fails (exception-safe).
    """
    fmt = "#{window_name}\t#{pane_dead}"
    rc, out, _ = _run(["tmux", "list-windows", "-t", session, "-F", fmt])
    if rc != 0:
        return False, False
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        name, dead_flag = parts
        if name == wt_name:
            return True, dead_flag.strip() == "1"
    return False, False


def terminal_signal_exists(signal_dir: pathlib.Path, wt_name: str) -> str | None:
    for suf in (".done", ".shutdown", ".failed", ".needs-restart"):
        if (signal_dir / f"{wt_name}{suf}").exists():
            return suf
    return None


def load_task_ids(
    config_path: pathlib.Path | None,
    wt_name: str,
    wp_id_override: str | None,
) -> tuple[list[str], str]:
    if not config_path or not config_path.exists():
        return [], "config-missing"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], "config-unreadable"

    target = wp_id_override
    if not target:
        suffix = data.get("window_suffix", "") or ""
        target = wt_name[: -len(suffix)] if suffix and wt_name.endswith(suffix) else wt_name

    for wp in data.get("wps", []) or []:
        if wp.get("wp_id") == target:
            return list(wp.get("tasks", [])), "config-ok"
    return [], f"wp-not-found:{target}"


def wait_for_workers(
    signal_dir: pathlib.Path,
    task_ids: list[str],
    max_wait: int,
    poll_interval: int,
    log_path: pathlib.Path,
) -> tuple[bool, list[str]]:
    """Return (settled, still_active)."""
    deadline = time.time() + max_wait
    poll_interval = max(5, min(poll_interval, 30))

    def _task_active(tid: str) -> bool:
        for suf in (".done", ".failed", ".bypassed"):
            if (signal_dir / f"{tid}{suf}").exists():
                return False
        running = signal_dir / f"{tid}.running"
        if not running.exists():
            return False
        try:
            age = time.time() - running.stat().st_mtime
        except OSError:
            return False
        return age < HEARTBEAT_GRACE_SEC

    while True:
        if task_ids:
            active = [t for t in task_ids if _task_active(t)]
        else:
            active = []
            for running in signal_dir.glob("*.running"):
                try:
                    age = time.time() - running.stat().st_mtime
                except OSError:
                    continue
                if age < HEARTBEAT_GRACE_SEC:
                    active.append(running.stem)
        if not active:
            return True, []
        if time.time() >= deadline:
            _log(log_path, f"settle timeout, still_active={active}")
            return False, active
        time.sleep(poll_interval)


def run_autopsy(
    plugin_root: str,
    session: str,
    wt_name: str,
    signal_dir: pathlib.Path,
    log_path: pathlib.Path,
) -> tuple[int, str | None]:
    if not plugin_root:
        return -1, None
    script = pathlib.Path(plugin_root) / "scripts" / "leader-autopsy.py"
    if not script.exists():
        _log(log_path, f"autopsy script missing: {script}")
        return -1, None
    try:
        r = subprocess.run(
            [sys.executable, str(script), session, wt_name, str(signal_dir)],
            capture_output=True, text=True, timeout=DEFAULT_AUTOPSY_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        _log(log_path, "autopsy TIMEOUT")
        return -1, None
    dump_dir: str | None = None
    if r.stdout.strip():
        try:
            dump_dir = json.loads(r.stdout.splitlines()[-1]).get("dump_dir")
        except (json.JSONDecodeError, IndexError):
            pass
    _log(log_path, f"autopsy rc={r.returncode} dump={dump_dir}")
    return r.returncode, dump_dir


def write_needs_restart(signal_dir: pathlib.Path, wt_name: str, payload: dict) -> pathlib.Path:
    target = signal_dir / f"{wt_name}.needs-restart"
    tmp = signal_dir / f"{wt_name}.needs-restart.tmp"
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    try:
        tmp.replace(target)
    except OSError:
        import shutil
        shutil.copy2(str(tmp), str(target))
        tmp.unlink(missing_ok=True)
    return target


def main() -> int:
    ap = argparse.ArgumentParser(
        description="WP leader watchdog (zero-LLM). On leader death: wait for workers to settle, then write .needs-restart."
    )
    ap.add_argument("session")
    ap.add_argument("wt_name")
    ap.add_argument("signal_dir")
    ap.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL,
                    help=f"poll interval seconds (default: {DEFAULT_POLL_INTERVAL})")
    ap.add_argument("--confirm-streak", type=int, default=DEFAULT_CONFIRM_STREAK,
                    help=f"consecutive dead detections required (default: {DEFAULT_CONFIRM_STREAK})")
    ap.add_argument("--worker-settle-timeout", type=int, default=DEFAULT_WORKER_SETTLE_TIMEOUT,
                    help=f"max seconds to wait for workers (default: {DEFAULT_WORKER_SETTLE_TIMEOUT})")
    ap.add_argument("--plugin-root", default=os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    ap.add_argument("--config", default=None,
                    help="wp-setup-config.json path for per-WP task list")
    ap.add_argument("--wp-id", default=None)
    ap.add_argument("--no-autopsy", action="store_true")
    args = ap.parse_args()

    signal_dir = pathlib.Path(normalize_path(args.signal_dir))
    signal_dir.mkdir(parents=True, exist_ok=True)
    log_path = signal_dir / f"{args.wt_name}.watchdog.log"

    _log(log_path,
         f"start pid={os.getpid()} session={args.session} wt={args.wt_name} "
         f"interval={args.interval}s confirm={args.confirm_streak} "
         f"settle_timeout={args.worker_settle_timeout}s")

    dead_streak = 0
    while True:
        term = terminal_signal_exists(signal_dir, args.wt_name)
        if term:
            _log(log_path, f"terminal signal {term} — exiting")
            return 0
        win_exists, is_dead = check_window_and_pane(args.session, args.wt_name)
        if not win_exists:
            _log(log_path, "window vanished — exiting")
            return 0
        if is_dead:
            dead_streak += 1
            _log(log_path, f"leader dead (streak={dead_streak}/{args.confirm_streak})")
            if dead_streak >= args.confirm_streak:
                break
        else:
            if dead_streak:
                _log(log_path, "leader alive again — streak reset")
            dead_streak = 0
        time.sleep(max(5, args.interval))

    # Final re-check before action (guard against race with normal completion).
    term = terminal_signal_exists(signal_dir, args.wt_name)
    if term:
        _log(log_path, f"terminal signal {term} appeared just before action — exiting")
        return 0

    autopsy_rc, autopsy_dir = (-1, None)
    if not args.no_autopsy:
        autopsy_rc, autopsy_dir = run_autopsy(
            args.plugin_root, args.session, args.wt_name, signal_dir, log_path
        )

    config_path = pathlib.Path(normalize_path(args.config)) if args.config else None
    task_ids, config_status = load_task_ids(config_path, args.wt_name, args.wp_id)
    _log(log_path,
         f"settle: config={config_status} tracking={len(task_ids)} ids={task_ids}")

    settled, still_active = wait_for_workers(
        signal_dir, task_ids,
        max_wait=args.worker_settle_timeout,
        poll_interval=args.interval,
        log_path=log_path,
    )

    payload = {
        "wt_name": args.wt_name,
        "session": args.session,
        "reason": "leader-death",
        "detected_at": _now_iso(),
        "confirm_streak": args.confirm_streak,
        "poll_interval_s": args.interval,
        "workers_settled": settled,
        "workers_still_active_on_timeout": still_active,
        "tracked_task_ids": task_ids,
        "config_status": config_status,
        "autopsy_rc": autopsy_rc,
        "autopsy_dir": autopsy_dir,
    }
    marker = write_needs_restart(signal_dir, args.wt_name, payload)
    _log(log_path, f"needs-restart written: {marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
