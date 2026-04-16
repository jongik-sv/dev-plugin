#!/usr/bin/env python3
"""graceful-shutdown.py — Cross-platform WP window shutdown.

Replaces the bash for-loop in dev-team SKILL.md. Uses absolute pane IDs
(collected via list-panes) instead of `${SESSION}:${WT_NAME}` target syntax,
which avoids dot-in-name parsing hazards and psmux target-resolution quirks.

Sequence:
  1. Write .shutdown marker (identifies user-initiated stop vs Leader Death)
  2. Send Escape to each pane (cancel any in-flight Claude prompt)
  3. Send /exit + Enter (graceful Claude termination)
  4. Wait graceful-timeout seconds
  5. kill-window (force cleanup of stragglers)

Usage:
  graceful-shutdown.py <session> <wt_name> <signal_dir> [--reason MSG] [--grace SECS]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import time

# Import cross-platform path normalizer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _platform import normalize_path


def find_mux_binary() -> str | None:
    """Prefer the one currently backing this session ($TMUX), fall back to PATH."""
    for name in ("tmux", "psmux"):
        p = shutil.which(name)
        if p:
            return p
    return None


def run(mux: str, *args: str, check: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run([mux, *args], check=check, capture_output=capture, text=True)


def list_pane_ids(mux: str, session: str, wt_name: str) -> list[str]:
    """Return absolute pane IDs for the given window, or [] if not found.

    Resolves window index first to avoid `session:name` ambiguity (dot in name,
    psmux target-parser quirks). Returns pane_id like `%28` which every tmux
    command accepts directly without further target resolution.
    """
    r = run(mux, "list-windows", "-t", session, "-F",
            "#{window_index}:#{window_name}", capture=True)
    if r.returncode != 0:
        return []
    win_idx = ""
    for line in r.stdout.strip().splitlines():
        # Match suffix only — window names may contain colons
        if line.endswith(f":{wt_name}"):
            win_idx = line.split(":", 1)[0]
            break
    if not win_idx:
        return []
    r = run(mux, "list-panes", "-t", f"{session}:{win_idx}",
            "-F", "#{pane_id}", capture=True)
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.strip().splitlines() if line.strip()]


def kill_window(mux: str, session: str, wt_name: str) -> None:
    r = run(mux, "list-windows", "-t", session, "-F",
            "#{window_index}:#{window_name}", capture=True)
    win_idx = ""
    for line in (r.stdout or "").strip().splitlines():
        if line.endswith(f":{wt_name}"):
            win_idx = line.split(":", 1)[0]
            break
    if win_idx:
        run(mux, "kill-window", "-t", f"{session}:{win_idx}")


def write_shutdown_marker(signal_dir: str, wt_name: str, reason: str) -> pathlib.Path:
    p = pathlib.Path(signal_dir)
    p.mkdir(parents=True, exist_ok=True)
    marker = p / f"{wt_name}.shutdown"
    marker.write_text(f"{reason}\n", encoding="utf-8")
    return marker


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session")
    ap.add_argument("wt_name")
    ap.add_argument("signal_dir")
    ap.add_argument("--reason", default="user-shutdown")
    ap.add_argument("--grace", type=float, default=3.0,
                    help="seconds to wait between /exit and kill-window")
    args = ap.parse_args()

    mux = find_mux_binary()
    if not mux:
        print("ERROR: neither tmux nor psmux on PATH", file=sys.stderr)
        return 1

    args.signal_dir = normalize_path(args.signal_dir)

    marker = write_shutdown_marker(args.signal_dir, args.wt_name, args.reason)
    print(f"[shutdown] marker: {marker}")

    pane_ids = list_pane_ids(mux, args.session, args.wt_name)
    if not pane_ids:
        print(f"[shutdown] no panes found for {args.session}:{args.wt_name} — skipping send-keys")
    else:
        print(f"[shutdown] {len(pane_ids)} pane(s): Escape")
        for pid in pane_ids:
            run(mux, "send-keys", "-t", pid, "Escape")
        print(f"[shutdown] {len(pane_ids)} pane(s): /exit Enter")
        for pid in pane_ids:
            run(mux, "send-keys", "-t", pid, "/exit", "Enter")

    if args.grace > 0:
        time.sleep(args.grace)

    kill_window(mux, args.session, args.wt_name)
    print(f"[shutdown] kill-window: {args.session}:{args.wt_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
