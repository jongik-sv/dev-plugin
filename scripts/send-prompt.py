#!/usr/bin/env python3
"""send-prompt.py — Cross-platform tmux/psmux prompt sender.

Sends a text prompt (and optionally Enter) to a tmux/psmux pane, handling
the bracketed-paste quirk that swallows the trailing Enter when text and
Enter are passed to `send-keys` in a single call.

Background:
  `send-keys -t PANE 'TEXT' Enter` in one call wraps the text in
  bracketed-paste markers (ESC[200~ ... ESC[201~). The Claude Code TUI
  treats the trailing CR as a newline INSIDE the paste block instead of
  submitting the prompt. This was first reported on Windows/psmux, but
  the same behavior has since been reproduced on macOS (tmux 3.6a +
  Claude Code v2.1.x) — the prompt text lands in the input buffer but is
  not submitted, so dev-team workers stayed idle until a second manual
  Enter was sent.

  Fix applied on ALL platforms: send text first, short sleep, then send
  Enter as a separate `send-keys` invocation so the Enter arrives outside
  the paste block and is interpreted as submit.

Usage:
  send-prompt.py <pane_id> --text "TEXT"               send text + Enter
  send-prompt.py <pane_id> --text "TEXT" --no-enter    send text only
  send-prompt.py <pane_id> --key <keyname>             send a single key
                                                       (e.g. Enter, Escape)
  send-prompt.py <pane_id> --slash-command <name>      send "/<name>" + Enter
                                                       (avoids MSYS2 argv
                                                       path-mangling of leading
                                                       slashes in Git Bash)

Exit codes:
  0 = ok
  2 = usage error
  other = underlying send-keys failure
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _platform import IS_WINDOWS  # noqa: E402


SPLIT_DELAY_SEC = 0.3


def mux_bin() -> str:
    """Return tmux/psmux binary path (psmux on Windows, tmux elsewhere)."""
    bin_name = "psmux" if IS_WINDOWS else "tmux"
    path = shutil.which(bin_name)
    if path is None:
        raise RuntimeError(f"{bin_name} not found on PATH")
    return path


def _run(args: list[str]) -> int:
    return subprocess.run(args, check=False).returncode


def send(pane_id: str, text: str | None, key: str | None,
         slash_command: str | None, enter: bool) -> int:
    mux = mux_bin()

    if key is not None:
        return _run([mux, "send-keys", "-t", pane_id, key])

    if slash_command is not None:
        # Reconstruct "/<name>" here so the argv crossing the shell boundary
        # never contains a leading slash — avoids MSYS2 Git-Bash path-mangling
        # that turns '/clear' into 'C:/Program Files/Git/clear'.
        text = "/" + slash_command.lstrip("/")

    if text is None:
        print("send-prompt.py: --text, --key, or --slash-command required", file=sys.stderr)
        return 2

    if enter:
        rc = _run([mux, "send-keys", "-t", pane_id, text])
        if rc != 0:
            return rc
        time.sleep(SPLIT_DELAY_SEC)
        return _run([mux, "send-keys", "-t", pane_id, "Enter"])

    return _run([mux, "send-keys", "-t", pane_id, text])


def main() -> int:
    p = argparse.ArgumentParser(
        description="Cross-platform tmux/psmux send-keys for Claude Code TUI prompts."
    )
    p.add_argument("pane_id", help="Absolute pane id (e.g. %%7) or target spec")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to send (followed by Enter unless --no-enter)")
    group.add_argument("--key", help="A single key name to send (Enter, Escape, ...)")
    group.add_argument("--slash-command", dest="slash_command", metavar="NAME",
                       help="Send a Claude slash command '/NAME' (e.g. clear, exit). "
                            "The leading slash is added internally to avoid "
                            "MSYS2 Git-Bash argv path-mangling on Windows.")
    p.add_argument("--no-enter", dest="enter", action="store_false",
                   help="Do not send Enter after --text")
    p.set_defaults(enter=True)
    args = p.parse_args()

    try:
        return send(args.pane_id, args.text, args.key, args.slash_command, args.enter)
    except RuntimeError as e:
        print(f"send-prompt.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
