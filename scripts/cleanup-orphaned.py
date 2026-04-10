#!/usr/bin/env python3
"""cleanup-orphaned.py — Kill orphaned vitest/tsc processes not belonging to active worktrees.

Cross-platform: macOS, Linux, Windows.
Usage:
  python3 cleanup-orphaned.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
import subprocess
import platform


def get_active_worktrees() -> list[str]:
    """Return list of active git worktree paths."""
    try:
        r = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
        paths = []
        for line in r.stdout.splitlines():
            if line.startswith("worktree "):
                paths.append(line[len("worktree "):].strip())
        return paths
    except FileNotFoundError:
        return []


def find_target_processes() -> list[dict]:
    """Find vitest/tsc processes. Returns list of {pid, name, cwd}."""
    system = platform.system()
    results = []

    if system == "Windows":
        # Use wmic to find node processes, then filter by command line
        try:
            r = subprocess.run(
                ["wmic", "process", "where",
                 "name='node.exe'",
                 "get", "ProcessId,CommandLine", "/format:csv"],
                capture_output=True, text=True, check=False,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("Node"):
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                cmdline = parts[1]
                pid_str = parts[2].strip()
                if any(kw in cmdline.lower() for kw in ("vitest", "tsc")):
                    cwd = _get_cwd_windows(pid_str)
                    results.append({"pid": int(pid_str), "name": cmdline[:80], "cwd": cwd})
        except FileNotFoundError:
            # Try powershell fallback
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Process -Name node -ErrorAction SilentlyContinue | "
                     "ForEach-Object { $_.Id.ToString() + '|' + "
                     "(Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine }"],
                    capture_output=True, text=True, check=False,
                )
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if "|" not in line:
                        continue
                    pid_str, cmdline = line.split("|", 1)
                    if any(kw in cmdline.lower() for kw in ("vitest", "tsc")):
                        cwd = _get_cwd_windows(pid_str.strip())
                        results.append({"pid": int(pid_str), "name": cmdline[:80], "cwd": cwd})
            except FileNotFoundError:
                pass

    else:
        # macOS / Linux — use ps
        try:
            r = subprocess.run(
                ["ps", "-eo", "pid,ppid,command"],
                capture_output=True, text=True, check=False,
            )
            for line in r.stdout.splitlines()[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                pid_str, ppid_str, cmd = parts
                if any(kw in cmd.lower() for kw in ("vitest", "tsc")):
                    cwd = _get_cwd_unix(pid_str)
                    results.append({
                        "pid": int(pid_str),
                        "ppid": int(ppid_str),
                        "name": cmd[:80],
                        "cwd": cwd,
                    })
        except FileNotFoundError:
            pass

    return results


def _get_cwd_unix(pid: str) -> str:
    """Get process CWD on macOS/Linux."""
    # Linux: /proc/{pid}/cwd
    proc_path = f"/proc/{pid}/cwd"
    if os.path.exists(proc_path):
        try:
            return os.readlink(proc_path)
        except OSError:
            pass

    # macOS: lsof -p {pid}
    try:
        r = subprocess.run(
            ["lsof", "-p", pid, "-Fn"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        # lsof -Fn output: lines starting with 'n' after 'fcwd' line
        lines = r.stdout.splitlines()
        for i, line in enumerate(lines):
            if line == "fcwd" and i + 1 < len(lines):
                return lines[i + 1].lstrip("n")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ""


def _get_cwd_windows(pid: str) -> str:
    """Get process CWD on Windows (best effort)."""
    # Windows doesn't expose CWD easily; skip CWD check and use PPID=1 heuristic
    return ""


def is_orphan(proc: dict, active_worktrees: list[str]) -> bool:
    """Determine if a process is orphaned."""
    cwd = proc.get("cwd", "")

    # If CWD is known, check if it belongs to an active worktree
    if cwd:
        for wt in active_worktrees:
            if cwd.startswith(wt):
                return False
        return True

    # If CWD unknown, check PPID (Unix only)
    ppid = proc.get("ppid", -1)
    if ppid == 1:
        return True

    # Can't determine — skip (don't kill unknowns)
    return False


def kill_process(pid: int) -> bool:
    """Kill a process by PID."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, check=False,
            )
        else:
            os.kill(pid, 15)  # SIGTERM
        return True
    except (OSError, ProcessLookupError):
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    active_worktrees = get_active_worktrees()
    processes = find_target_processes()

    orphans = [p for p in processes if is_orphan(p, active_worktrees)]

    if not orphans:
        print("고아 프로세스 없음")
        return

    print(f"고아 프로세스 {len(orphans)}개 발견:")
    for p in orphans:
        cwd_info = f" CWD={p['cwd']}" if p.get("cwd") else ""
        print(f"  PID={p['pid']}{cwd_info} {p['name']}")

    if dry_run:
        print("(--dry-run: 종료하지 않음)")
        return

    killed = 0
    for p in orphans:
        if kill_process(p["pid"]):
            killed += 1
            print(f"  → PID={p['pid']} 종료됨")
        else:
            print(f"  → PID={p['pid']} 종료 실패")

    print(f"완료: {killed}/{len(orphans)}개 종료")


if __name__ == "__main__":
    main()
