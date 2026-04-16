#!/usr/bin/env python3
"""graceful-shutdown.py — Cross-platform WP window shutdown.

Resolves the target to an absolute `window_id` (`@N`) and issues every
subsequent command against that ID (or `%pane_id`). Never uses
`session:name` target strings, which are vulnerable to tmux prefix
matching and silent fallback-to-active-window resolution (the exact
failure mode that caused team-leader self-kill during merge cleanup).

Resolution strategy (Mac/Linux tmux and Windows psmux all supported):
  1. `display-message -t session:=name` — tmux exact-match syntax
  2. Fallback: scan `list-windows` for an exact window_name match
     (psmux may not support `=name`)

Self-protection (default ON):
  Compares the resolved target window_id against the caller's own
  window (via $TMUX_PANE) and aborts if they match. Prevents a team
  leader from killing its own window during cleanup.

Windows short-circuit:
  On Windows (psmux), this script is a no-op that returns 0 without
  touching any window. psmux의 window 해석 신뢰성 문제로 엉뚱한 창을
  kill하는 사고가 반복되어, Windows에서는 창 종료를 사용자에게 위임한다.
  Merge 등 후속 로직은 시그널 파일(`.done`) 기반이라 영향 없음.

Sequence (Mac/Linux only):
  1. (optional) Write .shutdown marker — skipped with --no-marker
  2. Send Escape to each pane (cancel any in-flight Claude prompt)
  3. Send /exit + Enter (graceful Claude termination)
  4. Wait graceful-timeout seconds
  5. kill-window via absolute window_id

Usage:
  graceful-shutdown.py <session> <wt_name> <signal_dir>
                       [--reason MSG] [--grace SECS]
                       [--no-marker] [--allow-self-kill]
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
from _platform import normalize_path, IS_WINDOWS


def find_mux_binary() -> str | None:
    """Prefer the one currently backing this session ($TMUX), fall back to PATH."""
    for name in ("tmux", "psmux"):
        p = shutil.which(name)
        if p:
            return p
    return None


def run(mux: str, *args: str, check: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run([mux, *args], check=check, capture_output=capture, text=True)


def current_window_id(mux: str) -> str | None:
    """Return the window_id of the caller's current pane, or None if outside tmux."""
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None
    r = run(mux, "display-message", "-t", pane, "-p", "#{window_id}", capture=True)
    if r.returncode != 0:
        return None
    wid = r.stdout.strip()
    return wid if wid.startswith("@") else None


def resolve_window_id(mux: str, session: str, wt_name: str) -> str | None:
    """Return absolute window_id (`@N`) for session:wt_name, or None if absent.

    Tries tmux `=name` exact-match first, then **verifies** the returned
    window's name matches the request. This backstop is required because
    psmux silently falls back to the active window on `=name` miss (real
    tmux returns error in that case). Without the check, the fast path is
    itself a self-kill hazard.

    Falls back to a full `list-windows` scan with exact name comparison
    if the fast path's result doesn't verify. Never returns the active
    window on a miss — callers must handle None as "not found".
    """
    # Fast path: =name exact-match + result verification
    r = run(mux, "display-message", "-t", f"{session}:={wt_name}",
            "-p", "#{window_id}\t#{window_name}", capture=True)
    if r.returncode == 0:
        parts = r.stdout.strip().split("\t", 1)
        if len(parts) == 2 and parts[0].startswith("@") and parts[1] == wt_name:
            return parts[0]
    # Fallback: enumerate windows, tab-separated to avoid ambiguity with
    # names that contain colons.
    r = run(mux, "list-windows", "-t", session, "-F",
            "#{window_id}\t#{window_name}", capture=True)
    if r.returncode != 0:
        return None
    for line in r.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[1] == wt_name:
            return parts[0]
    return None


def list_panes_in_window(mux: str, window_id: str) -> list[str]:
    """List pane IDs inside the given window_id. Uses absolute target — no resolution fallback."""
    r = run(mux, "list-panes", "-t", window_id, "-F", "#{pane_id}", capture=True)
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.strip().splitlines() if line.strip()]


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
    ap.add_argument("--no-marker", action="store_true",
                    help="Skip .shutdown marker write (merge-cleanup path). "
                         "The marker distinguishes user-initiated shutdown "
                         "from other close paths; merge cleanup does not want it.")
    ap.add_argument("--allow-self-kill", action="store_true",
                    help="Disable the self-protection guard. Without this flag "
                         "the script aborts if the target window equals the "
                         "caller's own window (prevents team-leader self-kill).")
    args = ap.parse_args()

    if IS_WINDOWS:
        # psmux window 해석 신뢰성 문제로 엉뚱한 창을 kill하는 사고가 반복되어
        # Windows에서는 WP 창 종료를 수행하지 않는다. 필요 시 사용자가 수동 종료한다.
        # Merge는 `.done` 시그널 기반이라 창 생존과 무관하게 정상 동작.
        print(f"[shutdown] Windows: kill skipped for {args.wt_name} "
              f"(reason={args.reason}). Close window manually if needed.")
        return 0

    mux = find_mux_binary()
    if not mux:
        print("ERROR: neither tmux nor psmux on PATH", file=sys.stderr)
        return 1

    args.signal_dir = normalize_path(args.signal_dir)

    target_wid = resolve_window_id(mux, args.session, args.wt_name)
    if not target_wid:
        print(f"[shutdown] window not found: {args.session}:{args.wt_name} "
              "(already closed?)")
        return 0

    if not args.allow_self_kill:
        own_wid = current_window_id(mux)
        if own_wid and own_wid == target_wid:
            print(f"[shutdown] ABORT: target {args.wt_name} ({target_wid}) "
                  "is the caller's own window — self-protection triggered. "
                  "Pass --allow-self-kill to override.", file=sys.stderr)
            return 2

    if not args.no_marker:
        marker = write_shutdown_marker(args.signal_dir, args.wt_name, args.reason)
        print(f"[shutdown] marker: {marker}")

    pane_ids = list_panes_in_window(mux, target_wid)
    if not pane_ids:
        print(f"[shutdown] no panes in {args.wt_name} ({target_wid}) — skipping send-keys")
    else:
        print(f"[shutdown] {len(pane_ids)} pane(s): Escape")
        for pid in pane_ids:
            run(mux, "send-keys", "-t", pid, "Escape")
        print(f"[shutdown] {len(pane_ids)} pane(s): /exit Enter")
        # On Windows/psmux, send-keys 'TEXT' Enter in a single call gets wrapped
        # in bracketed-paste markers and Claude Code TUI treats the trailing
        # Enter as a literal newline instead of submit — split into two calls
        # with a small delay. macOS/Linux tmux does not need this.
        if IS_WINDOWS:
            for pid in pane_ids:
                run(mux, "send-keys", "-t", pid, "/exit")
            time.sleep(0.3)
            for pid in pane_ids:
                run(mux, "send-keys", "-t", pid, "Enter")
        else:
            for pid in pane_ids:
                run(mux, "send-keys", "-t", pid, "/exit", "Enter")

    if args.grace > 0:
        time.sleep(args.grace)

    rc = run(mux, "kill-window", "-t", target_wid).returncode
    print(f"[shutdown] kill-window: {args.wt_name} ({target_wid}) rc={rc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
