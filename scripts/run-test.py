#!/usr/bin/env python3
"""run-test.py — Run a test command with timeout and process-group cleanup.

Cross-platform: macOS, Linux, Windows.
Usage:
  python3 run-test.py <timeout_secs> -- <command...>
  python3 run-test.py 300 -- npx vitest run
  python3 run-test.py 900 -- npx playwright test

- Runs the command in a new process group.
- On completion, timeout, or parent signal: kills the entire process group.
- Captures output and prints last 200 lines.
- Exit codes: original exit code on success, 124 on timeout.
"""
from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import platform
import threading
from collections import deque

TAIL_LINES = 200


def main():
    if "--" not in sys.argv:
        print("Usage: run-test.py <timeout_secs> -- <command...>", file=sys.stderr)
        sys.exit(1)

    sep = sys.argv.index("--")
    timeout_secs = int(sys.argv[1]) if sep > 1 else 300
    cmd = sys.argv[sep + 1:]

    if not cmd:
        print("Error: no command specified", file=sys.stderr)
        sys.exit(1)

    is_windows = platform.system() == "Windows"

    kwargs: dict = {}
    if is_windows:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        cmd if is_windows else shlex.join(cmd),
        shell=not is_windows,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kwargs,
    )

    pgid = None
    if not is_windows:
        try:
            pgid = os.getpgid(proc.pid)
        except OSError:
            pgid = proc.pid

    def kill_group(sig=signal.SIGTERM):
        try:
            if is_windows:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True, check=False,
                )
            elif pgid:
                os.killpg(pgid, sig)
        except (OSError, ProcessLookupError):
            pass

    def on_signal(sig, frame):
        kill_group()
        sys.exit(128 + sig)

    if not is_windows:
        signal.signal(signal.SIGHUP, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

    # Read stdout in a thread to avoid pipe buffer deadlock
    tail: deque[str] = deque(maxlen=TAIL_LINES)

    def reader():
        for line in proc.stdout:
            try:
                tail.append(line.decode("utf-8", errors="replace").rstrip("\n\r"))
            except Exception:
                tail.append(str(line))

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    # Wait with timeout
    timed_out = False
    try:
        proc.wait(timeout=timeout_secs)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            kill_group(signal.SIGKILL)
            proc.kill()
            proc.wait()

    t.join(timeout=3)

    # Print captured output
    for line in tail:
        print(line)

    if timed_out:
        print(f"\n[run-test] TIMEOUT: {timeout_secs}s 초과 — 프로세스 그룹 종료됨")
        sys.exit(124)

    # Normal completion: kill any lingering children
    kill_group()
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    main()
