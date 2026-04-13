#!/usr/bin/env python3
"""e2e-server.py — E2E server lifecycle management.

Cross-platform: macOS, Linux, Windows.
Usage:
  python3 e2e-server.py check --url http://localhost:3000
  python3 e2e-server.py start --cmd "pnpm dev" --url http://localhost:3000 [--timeout 120]
  python3 e2e-server.py stop  --url http://localhost:3000

check:
  Exit 0 if URL responds (any HTTP status), exit 1 otherwise.

start:
  1. If URL already responds -> exit 0 (already running)
  2. Start server in background (new process group)
  3. Poll URL every 2s until responsive or timeout
  4. PID file: {tempdir}/e2e-server-{port}.pid
  5. Server log: {tempdir}/e2e-server-{port}.log
  Exit 0 on success, 1 on timeout/crash.

stop:
  Kill server process group. PID file derived from --url.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen


def _derive_paths(url: str):
    """Derive PID and log file paths from URL port."""
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base = os.path.join(tempfile.gettempdir(), f"e2e-server-{port}")
    return f"{base}.pid", f"{base}.log"


def _health_check(url: str, timeout: int = 5) -> bool:
    """Check if something is listening at URL. Any HTTP response = running."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        urlopen(url, timeout=timeout, context=ctx)
        return True
    except HTTPError:
        return True  # 4xx/5xx = server IS running
    except (URLError, OSError):
        return False


def _kill_pid(pid: int):
    """Kill a process and its group."""
    is_windows = platform.system() == "Windows"
    try:
        if is_windows:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                capture_output=True, check=False,
            )
        else:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def _read_tail(path: str, n: int) -> list:
    """Read last n lines from a file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [line.rstrip("\n\r") for line in lines[-n:]]
    except OSError:
        return []


def _cleanup_pid(pid_file: str):
    """Remove PID file if it exists."""
    try:
        os.remove(pid_file)
    except OSError:
        pass


def cmd_check(args):
    """Check if server is running."""
    alive = _health_check(args.url)
    result = {"status": "running" if alive else "not_running", "url": args.url}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if alive else 1)


def cmd_start(args):
    """Start server and wait for health check."""
    url = args.url
    timeout = args.timeout
    pid_file, log_path = _derive_paths(url)

    # Already running?
    if _health_check(url):
        print(json.dumps({
            "status": "already_running", "url": url, "started": False,
        }))
        sys.exit(0)

    # Start server
    is_windows = platform.system() == "Windows"
    kwargs = {}
    if is_windows:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        args.cmd,
        shell=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        **kwargs,
    )

    # Write PID
    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    # Poll health check
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check if process died
        if proc.poll() is not None:
            log_file.close()
            tail = _read_tail(log_path, 20)
            print(json.dumps({
                "status": "server_crashed", "url": url,
                "exit_code": proc.returncode,
                "elapsed": round(time.time() - start_time, 1),
                "log_tail": tail,
            }))
            _cleanup_pid(pid_file)
            sys.exit(1)

        if _health_check(url, timeout=3):
            elapsed = round(time.time() - start_time, 1)
            print(json.dumps({
                "status": "started", "url": url,
                "pid": proc.pid, "pid_file": pid_file,
                "elapsed": elapsed, "started": True,
            }))
            sys.exit(0)

        time.sleep(2)

    # Timeout — kill server
    log_file.close()
    _kill_pid(proc.pid)
    tail = _read_tail(log_path, 20)
    _cleanup_pid(pid_file)
    print(json.dumps({
        "status": "timeout", "url": url,
        "timeout": timeout,
        "log_tail": tail,
    }))
    sys.exit(1)


def cmd_stop(args):
    """Stop server by PID file derived from URL."""
    pid_file, _ = _derive_paths(args.url)
    if not os.path.isfile(pid_file):
        print(json.dumps({"status": "no_pid_file", "url": args.url}))
        sys.exit(0)

    with open(pid_file, "r") as f:
        pid = int(f.read().strip())

    _kill_pid(pid)
    _cleanup_pid(pid_file)
    print(json.dumps({"status": "stopped", "pid": pid}))
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="E2E server lifecycle management")
    sub = parser.add_subparsers(dest="command")

    check_p = sub.add_parser("check", help="Check if server is running")
    check_p.add_argument("--url", required=True, help="Server URL to health-check")

    start_p = sub.add_parser("start", help="Start server and wait for ready")
    start_p.add_argument("--cmd", required=True, help="Server start command")
    start_p.add_argument("--url", required=True, help="Server URL to health-check")
    start_p.add_argument(
        "--timeout", type=int, default=120,
        help="Max seconds to wait for server ready (default: 120)",
    )

    stop_p = sub.add_parser("stop", help="Stop server")
    stop_p.add_argument("--url", required=True, help="Server URL (derives PID file path)")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
