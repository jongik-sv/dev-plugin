#!/usr/bin/env python3
"""WP Leader autopsy — dump forensic data when a WP leader dies unexpectedly.

Zero-LLM: called by the team leader's monitoring loop at Leader Death detection.
Produces docs/dev-team/autopsy/{WT_NAME}-{timestamp}/ containing:
  - pane-scrollback.txt   : tmux capture-pane output (default, ~0.5-2 MB)
  - signals-snapshot/     : WP/task signal files at moment of death (~50 KB)
  - git-state.txt         : git log/status/diff on worktree (~10-100 KB)
  - env.txt               : tmux pane/window info, uname, timestamp (~1-5 KB)
  - summary.txt           : compact digest (<2 KB) — ONLY file the team leader reads
  - transcript.jsonl      : optional (--include-transcript, ~2-10 MB)
  - transcript-tail.jsonl : optional (--transcript-tail N)

Cost-effective default: transcript OMITTED. Use --include-transcript or
--transcript-tail only when pane-scrollback + signals don't reveal the cause.

Standard library only; no pip dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _write_text(path: Path, body: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def _run(cmd, cwd=None, timeout=10):
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except FileNotFoundError as e:
        return -2, "", f"FileNotFoundError: {e}"
    except Exception as e:  # noqa: BLE001
        return -3, "", f"{type(e).__name__}: {e}"


def capture_pane(session: str, wt_name: str, out_path: Path, lines: int = 5000) -> int:
    target = f"{session}:{wt_name}.0"
    rc, out, err = _run(
        ["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{lines}"]
    )
    body = out if rc == 0 and out else f"# capture-pane failed rc={rc} err={err}\n"
    _write_text(out_path, body)
    return len(body)


def snapshot_signals(shared_signal_dir: str, wt_name: str, out_dir: Path) -> int:
    src = Path(shared_signal_dir)
    if not src.exists():
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    suffixes = {".done", ".failed", ".running", ".bypassed", ".shutdown"}
    for f in src.iterdir():
        if not f.is_file():
            continue
        name = f.name
        match_wp = name.startswith(f"{wt_name}.")
        match_task = f.suffix in suffixes
        if not (match_wp or match_task):
            continue
        try:
            shutil.copy2(f, out_dir / name)
            count += 1
        except OSError:
            pass
    return count


def capture_git_state(worktree_path: str, out_path: Path) -> None:
    lines = [f"# git state for {worktree_path}"]
    if not Path(worktree_path).exists():
        lines.append(f"\n(worktree path not found: {worktree_path})")
        _write_text(out_path, "\n".join(lines) + "\n")
        return
    queries = [
        ("branch", ["git", "branch", "--show-current"]),
        ("log main..HEAD --oneline", ["git", "log", "main..HEAD", "--oneline"]),
        ("status --short", ["git", "status", "--short"]),
        ("diff --stat", ["git", "diff", "--stat"]),
        ("log -1 --stat", ["git", "log", "-1", "--stat"]),
    ]
    for label, cmd in queries:
        rc, out, err = _run(cmd, cwd=worktree_path)
        lines.append(f"\n## {label} (rc={rc})\n{(out or err).rstrip()}")
    _write_text(out_path, "\n".join(lines) + "\n")


def capture_env(session: str, wt_name: str, out_path: Path) -> None:
    target_pane = f"{session}:{wt_name}.0"
    target_win = f"{session}:{wt_name}"
    queries = [
        (
            "tmux pane",
            [
                "tmux",
                "display-message",
                "-t",
                target_pane,
                "-p",
                "pid=#{pane_pid} dead=#{pane_dead} current_cmd=#{pane_current_command} last_activity=#{pane_last_activity}",
            ],
        ),
        (
            "tmux window",
            [
                "tmux",
                "display-message",
                "-t",
                target_win,
                "-p",
                "window=#{window_name} idx=#{window_index} activity=#{window_activity}",
            ],
        ),
        ("uname -a", ["uname", "-a"]),
        ("date utc", ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]),
    ]
    lines = []
    for label, cmd in queries:
        rc, out, err = _run(cmd)
        lines.append(f"## {label} (rc={rc})\n{(out or err).rstrip()}")
    _write_text(out_path, "\n".join(lines) + "\n")


def _encode_project_path(project_dir: str) -> str:
    """Claude Code encodes project paths as `-Users-jji-project-dev-plugin`."""
    return str(Path(project_dir).resolve()).replace("/", "-")


def extract_transcript(project_dir: str, out_path: Path, tail: int | None = None) -> str | None:
    root = Path.home() / ".claude" / "projects"
    if not root.exists():
        return None
    encoded = _encode_project_path(project_dir)
    candidates = [d for d in root.iterdir() if d.is_dir() and encoded in d.name]
    if not candidates:
        return None
    sessions = []
    for d in candidates:
        sessions.extend(d.glob("*.jsonl"))
    if not sessions:
        return None
    latest = max(sessions, key=lambda p: p.stat().st_mtime)
    try:
        if tail is None:
            shutil.copy2(latest, out_path)
        else:
            text = latest.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-tail:]
            _write_text(out_path, "\n".join(lines) + "\n")
    except OSError as e:
        return f"(copy failed: {e})"
    return str(latest)


def build_summary(
    dump_dir: Path,
    session: str,
    wt_name: str,
    pane_bytes: int,
    signal_count: int,
    transcript_src: str | None,
) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out: list[str] = [
        f"# Leader Autopsy — {wt_name}",
        f"- timestamp: {ts}",
        f"- session: {session}",
        f"- pane_scrollback_bytes: {pane_bytes}",
        f"- signals_captured: {signal_count}",
        f"- transcript_source: {transcript_src or '(omitted — rerun with --include-transcript if needed)'}",
    ]

    try:
        pane = (dump_dir / "pane-scrollback.txt").read_text(
            encoding="utf-8", errors="replace"
        )
        tail = pane.splitlines()[-40:]
    except OSError:
        tail = ["(pane-scrollback.txt unreadable)"]
    out.append("")
    out.append("## pane scrollback — last 40 lines")
    out.extend(tail)

    sig_dir = dump_dir / "signals-snapshot"
    if sig_dir.exists():
        buckets = {s: [] for s in ("running", "failed", "done", "bypassed", "shutdown")}
        for p in sig_dir.iterdir():
            suf = p.suffix.lstrip(".")
            if suf in buckets:
                buckets[suf].append(p.name)
        out.append("")
        out.append("## signals at death")
        for k in ("running", "failed", "bypassed", "done", "shutdown"):
            vals = sorted(buckets[k])
            out.append(f"- {k} (N={len(vals)}): {vals}")

    try:
        git_text = (dump_dir / "git-state.txt").read_text(
            encoding="utf-8", errors="replace"
        )
        git_head = git_text.splitlines()[:25]
    except OSError:
        git_head = ["(git-state.txt unreadable)"]
    out.append("")
    out.append("## git state — first 25 lines")
    out.extend(git_head)

    _write_text(dump_dir / "summary.txt", "\n".join(out) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(
        description="WP Leader autopsy — zero-LLM forensic dump on Leader Death",
    )
    p.add_argument("session", help="tmux session name")
    p.add_argument("wt_name", help="WP worktree/window name, e.g. WP-01 or WP-01-p1")
    p.add_argument("shared_signal_dir", help="shared signal directory absolute path")
    p.add_argument(
        "--worktree",
        default=None,
        help="worktree path (default: .claude/worktrees/{wt_name})",
    )
    p.add_argument(
        "--out-root",
        default="docs/dev-team/autopsy",
        help="output root (default: docs/dev-team/autopsy)",
    )
    p.add_argument("--scrollback-lines", type=int, default=5000)
    p.add_argument(
        "--include-transcript",
        action="store_true",
        help="copy full claude session transcript (~2-10 MB)",
    )
    p.add_argument(
        "--transcript-tail",
        type=int,
        default=None,
        help="copy only last N lines of transcript",
    )
    p.add_argument(
        "--project-dir",
        default=None,
        help="project dir for transcript lookup (default: cwd)",
    )
    args = p.parse_args()

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump_dir = Path(args.out_root) / f"{args.wt_name}-{ts}"
    dump_dir.mkdir(parents=True, exist_ok=True)

    pane_bytes = capture_pane(
        args.session,
        args.wt_name,
        dump_dir / "pane-scrollback.txt",
        lines=args.scrollback_lines,
    )
    signal_count = snapshot_signals(
        args.shared_signal_dir, args.wt_name, dump_dir / "signals-snapshot"
    )
    worktree = args.worktree or f".claude/worktrees/{args.wt_name}"
    capture_git_state(worktree, dump_dir / "git-state.txt")
    capture_env(args.session, args.wt_name, dump_dir / "env.txt")

    transcript_src: str | None = None
    if args.include_transcript or args.transcript_tail is not None:
        project_dir = args.project_dir or os.getcwd()
        out_name = (
            "transcript.jsonl" if args.include_transcript else "transcript-tail.jsonl"
        )
        transcript_src = extract_transcript(
            project_dir, dump_dir / out_name, tail=args.transcript_tail
        )

    build_summary(
        dump_dir, args.session, args.wt_name, pane_bytes, signal_count, transcript_src
    )

    print(
        json.dumps(
            {
                "ok": True,
                "dump_dir": str(dump_dir),
                "summary": str(dump_dir / "summary.txt"),
                "pane_bytes": pane_bytes,
                "signals_captured": signal_count,
                "transcript_source": transcript_src,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
