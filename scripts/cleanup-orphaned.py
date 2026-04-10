#!/usr/bin/env python3
"""cleanup-orphaned.py — Kill orphaned test processes not belonging to active worktrees.

Cross-platform: macOS, Linux, Windows.
Usage:
  python3 cleanup-orphaned.py [--dry-run] [--processes vitest,tsc]

If --processes is not given, reads Cleanup Processes from wbs.md Dev Config.
"""
from __future__ import annotations

import os
import re
import sys
import subprocess
import platform


def get_active_worktrees() -> list[str] | None:
    """Return list of active git worktree paths, or None on git failure."""
    try:
        r = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
        if r.returncode != 0:
            return None
        paths = []
        for line in r.stdout.splitlines():
            if line.startswith("worktree "):
                paths.append(line[len("worktree "):].strip())
        return paths
    except FileNotFoundError:
        return None


def find_target_processes(keywords: list) -> list[dict]:
    """Find processes matching keywords. Returns list of {pid, name, cwd}."""
    if not keywords:
        return []
    kw_lower = tuple(kw.lower() for kw in keywords)
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
                if any(kw in cmdline.lower() for kw in kw_lower):
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
                    if any(kw in cmdline.lower() for kw in kw_lower):
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
                if any(kw in cmd.lower() for kw in kw_lower):
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


def _load_cleanup_processes() -> list:
    """Try to load cleanup_processes from wbs.md Dev Config."""
    # Search for wbs.md in common locations
    candidates = ["docs/wbs.md"]
    # Also check docs/*/wbs.md for subprojects
    if os.path.isdir("docs"):
        for entry in os.listdir("docs"):
            p = os.path.join("docs", entry, "wbs.md")
            if os.path.isfile(p):
                candidates.append(p)

    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            # Inline minimal parser for Cleanup Processes line
            in_config = False
            in_cleanup = False
            for line in text.splitlines():
                if re.match(r'^##\s+Dev\s+Config\s*$', line, re.IGNORECASE):
                    in_config = True
                    continue
                if in_config and re.match(r'^##\s+', line) and not line.strip().startswith("###"):
                    if not re.match(r'^##\s+Dev\s+Config', line, re.IGNORECASE):
                        break
                if in_config and re.match(r'^###\s+Cleanup\s+Processes', line, re.IGNORECASE):
                    in_cleanup = True
                    continue
                if in_cleanup and line.strip().startswith("###"):
                    break
                if in_cleanup and line.strip() and not line.strip().startswith("---"):
                    return [p.strip() for p in line.strip().split(",") if p.strip()]
        except OSError:
            continue
    return []


def main():
    dry_run = "--dry-run" in sys.argv

    # Parse --processes arg
    keywords = None
    for i, arg in enumerate(sys.argv):
        if arg == "--processes" and i + 1 < len(sys.argv):
            keywords = [p.strip() for p in sys.argv[i + 1].split(",") if p.strip()]

    # If not provided, try to read from wbs.md Dev Config
    if keywords is None:
        keywords = _load_cleanup_processes()

    if not keywords:
        print("정리 대상 프로세스 없음 (Dev Config에 'Cleanup Processes' 미설정 또는 --processes 미지정)")
        return

    active_worktrees = get_active_worktrees()
    if active_worktrees is None:
        print("WARNING: git worktree list 실패 — 고아 프로세스 정리를 건너뜁니다")
        return
    processes = find_target_processes(keywords)

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
