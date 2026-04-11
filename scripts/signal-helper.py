#!/usr/bin/env python3
"""signal-helper.py — Atomic signal file create/check/wait.

Replaces signal-helper.sh for cross-platform support.
Usage identical to signal-helper.sh — see --help.
"""
import sys
import os
import time
import pathlib

MAX_LINES = 50

USAGE = """\
Usage: signal-helper.py <command> <id> <signal-dir> [message]

Commands:
  start        <id> <dir>            .running file create
  done         <id> <dir> [message]  .done file atomic create (.running removed)
  fail         <id> <dir> [message]  .failed file atomic create (.running removed)
  shutdown     <id> <dir> [reason]   .shutdown marker create (user-initiated graceful stop)
  check        <id> <dir>            status output (running|done|failed|shutdown|none)
  wait         <id> <dir> [timeout]  wait for .done or .failed (default timeout: unlimited)
  wait-running <id> <dir> [timeout]  wait for .running/.done/.failed (default timeout: 120s)
  heartbeat    <id> <dir>            touch .running file

Examples:
  signal-helper.py start TSK-01-01 /tmp/claude-signals/proj
  signal-helper.py done TSK-01-01 /tmp/claude-signals/proj "test: 5/5, commit: abc123"
  signal-helper.py fail TSK-01-01 /tmp/claude-signals/proj "Phase: test, Error: assertion failed"
  signal-helper.py shutdown WP-04 /tmp/claude-signals/proj "user-shutdown"
  signal-helper.py check TSK-01-01 /tmp/claude-signals/proj
  signal-helper.py wait TSK-01-01 /tmp/claude-signals/proj 600
  signal-helper.py wait-running TSK-01-01 /tmp/claude-signals/proj 120
  signal-helper.py heartbeat TSK-01-01 /tmp/claude-signals/proj
"""


def truncate(text: str) -> str:
    """Truncate text to MAX_LINES lines."""
    lines = text.split("\n")
    return "\n".join(lines[:MAX_LINES])


def read_truncated(path: pathlib.Path) -> str:
    """Read file content, truncated to MAX_LINES."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:MAX_LINES])


def main():
    if len(sys.argv) < 4:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]
    sig_id = sys.argv[2]
    sig_dir = pathlib.Path(sys.argv[3])
    msg = sys.argv[4] if len(sys.argv) > 4 else ""

    sig_dir.mkdir(parents=True, exist_ok=True)

    done_path = sig_dir / f"{sig_id}.done"
    failed_path = sig_dir / f"{sig_id}.failed"
    running_path = sig_dir / f"{sig_id}.running"
    shutdown_path = sig_dir / f"{sig_id}.shutdown"

    if cmd == "start":
        running_path.write_text("started\n", encoding="utf-8")
        print("OK:started")

    elif cmd == "done":
        content = truncate(msg or "\uc644\ub8cc")
        tmp_path = sig_dir / f"{sig_id}.done.tmp"
        tmp_path.write_text(content + "\n", encoding="utf-8")
        try:
            tmp_path.replace(done_path)
        except OSError:
            import shutil
            shutil.copy2(str(tmp_path), str(done_path))
            tmp_path.unlink(missing_ok=True)
        running_path.unlink(missing_ok=True)
        print("OK:done")

    elif cmd == "fail":
        content = truncate(msg or "\uc2e4\ud328")
        tmp_path = sig_dir / f"{sig_id}.failed.tmp"
        tmp_path.write_text(content + "\n", encoding="utf-8")
        try:
            tmp_path.replace(failed_path)
        except OSError:
            import shutil
            shutil.copy2(str(tmp_path), str(failed_path))
            tmp_path.unlink(missing_ok=True)
        running_path.unlink(missing_ok=True)
        print("OK:failed")

    elif cmd == "shutdown":
        reason = msg or "user-shutdown"
        import datetime
        content = truncate(f"reason: {reason}\nat: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
        tmp_path = sig_dir / f"{sig_id}.shutdown.tmp"
        tmp_path.write_text(content, encoding="utf-8")
        try:
            tmp_path.replace(shutdown_path)
        except OSError:
            import shutil
            shutil.copy2(str(tmp_path), str(shutdown_path))
            tmp_path.unlink(missing_ok=True)
        print("OK:shutdown")

    elif cmd == "check":
        if done_path.exists():
            print("done")
            print(read_truncated(done_path))
        elif failed_path.exists():
            print("failed")
            print(read_truncated(failed_path))
        elif shutdown_path.exists():
            print("shutdown")
            print(read_truncated(shutdown_path))
        elif running_path.exists():
            print("running")
        else:
            print("none")

    elif cmd == "wait":
        try:
            timeout = int(msg) if msg else 0  # 0 = unlimited
        except ValueError:
            print(f"ERROR: invalid timeout value: {msg}", file=sys.stderr)
            sys.exit(1)
        elapsed = 0
        interval = 5
        while not done_path.exists() and not failed_path.exists():
            if not sig_dir.exists():
                print(f"ERROR:signal_dir_missing:{sig_id} ({sig_dir})", file=sys.stderr)
                sys.exit(1)
            time.sleep(interval)
            elapsed += interval
            if elapsed % 300 == 0:
                print(f"waiting:{sig_id} ({elapsed}s elapsed)")
            if timeout > 0 and elapsed >= timeout:
                print(f"timeout:{sig_id} ({elapsed}s)")
                sys.exit(1)
        if done_path.exists():
            print(f"DONE:{sig_id}")
            print(read_truncated(done_path))
        else:
            print(f"FAILED:{sig_id}")
            print(read_truncated(failed_path))

    elif cmd == "wait-running":
        try:
            timeout = int(msg) if msg else 120
        except ValueError:
            print(f"ERROR: invalid timeout value: {msg}", file=sys.stderr)
            sys.exit(1)
        elapsed = 0
        interval = 2
        while not running_path.exists() and not done_path.exists() and not failed_path.exists():
            if not sig_dir.exists():
                print(f"ERROR:signal_dir_missing:{sig_id} ({sig_dir})", file=sys.stderr)
                sys.exit(1)
            time.sleep(interval)
            elapsed += interval
            if timeout > 0 and elapsed >= timeout:
                print(f"timeout:{sig_id} ({elapsed}s)")
                sys.exit(1)
        if done_path.exists():
            print(f"DONE:{sig_id}")
        elif failed_path.exists():
            print(f"FAILED:{sig_id}")
        else:
            print(f"RUNNING:{sig_id}")

    elif cmd == "heartbeat":
        running_path.touch()

    else:
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
