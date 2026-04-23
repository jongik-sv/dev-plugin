#!/usr/bin/env python3
"""init-git-rerere.py — Idempotent git rerere + merge driver setup.

Sets rerere.enabled, rerere.autoupdate, and registers two smart merge drivers:
  - merge.state-json-smart  (scripts/merge-state-json.py)
  - merge.wbs-status-smart  (scripts/merge-wbs-status.py)

Usage:
    python3 init-git-rerere.py [--worktree PATH]

Options:
    --worktree PATH   Git worktree directory (default: CWD). Uses
                      `git -C PATH config --local` so git-file (.git as a
                      file, as in worktrees) is handled transparently.

Environment:
    CLAUDE_PLUGIN_ROOT   Plugin root directory. Falls back to
                         Path(__file__).parent.parent when not set.

Exit codes:
    0   success (all set or all no-op)
    1   fatal error (git missing, not a git repo, etc.)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import pathlib


# ---------------------------------------------------------------------------
# plugin root resolution
# ---------------------------------------------------------------------------

def resolve_plugin_root() -> pathlib.Path:
    """Return the plugin root directory.

    Priority:
    1. CLAUDE_PLUGIN_ROOT environment variable
    2. Path(__file__).parent.parent  (scripts/ → plugin root)
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_val:
        candidate = pathlib.Path(env_val)
        # Normalize (strip trailing slash, resolve symlinks)
        candidate = candidate.resolve()
        if (candidate / "scripts").is_dir():
            return candidate
        # Still use it even if scripts/ doesn't exist, but warn
        print(
            f"[warn] CLAUDE_PLUGIN_ROOT={env_val!r} has no scripts/ subdir; "
            "using anyway",
            file=sys.stderr,
        )
        return candidate

    # Fallback: this file lives in {plugin_root}/scripts/
    fallback = pathlib.Path(__file__).resolve().parent.parent
    return fallback


# ---------------------------------------------------------------------------
# idempotent single-key setter
# ---------------------------------------------------------------------------

def set_config_idempotent(worktree: str, key: str, value: str) -> bool:
    """Set `key=value` in local git config if not already equal.

    Returns:
        True   — value was changed (or newly written)
        False  — value already matched; no-op

    Raises SystemExit(1) on git error.
    """
    # Read current value
    r_get = subprocess.run(
        ["git", "-C", worktree, "config", "--local", "--get", key],
        capture_output=True, text=True,
    )
    current = r_get.stdout.strip() if r_get.returncode == 0 else None

    if current == value:
        print(f"  [no-op] {key} = {value}")
        return False

    r_set = subprocess.run(
        ["git", "-C", worktree, "config", "--local", key, value],
        capture_output=True, text=True,
    )
    if r_set.returncode != 0:
        print(
            f"ERROR: git config --local {key} {value!r} failed "
            f"(rc={r_set.returncode}): {r_set.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  [set]   {key} = {value}")
    return True


# ---------------------------------------------------------------------------
# rerere configuration
# ---------------------------------------------------------------------------

def configure_rerere(worktree: str, _plugin_root: pathlib.Path) -> dict:
    """Set rerere.enabled and rerere.autoupdate.

    Returns: {"changed": int, "noop": int}
    """
    changed = 0
    noop = 0
    for key, val in [
        ("rerere.enabled", "true"),
        ("rerere.autoupdate", "true"),
    ]:
        if set_config_idempotent(worktree, key, val):
            changed += 1
        else:
            noop += 1
    return {"changed": changed, "noop": noop}


# ---------------------------------------------------------------------------
# merge driver configuration
# ---------------------------------------------------------------------------

def configure_merge_drivers(worktree: str, plugin_root: pathlib.Path) -> dict:
    """Register state-json-smart and wbs-status-smart merge drivers.

    Returns: {"changed": int, "noop": int}
    """
    python_bin = sys.executable
    state_json_script = str(plugin_root / "scripts" / "merge-state-json.py")
    wbs_status_script = str(plugin_root / "scripts" / "merge-wbs-status.py")

    drivers = [
        # (key, value)
        (
            "merge.state-json-smart.driver",
            f'"{python_bin}" "{state_json_script}" %O %A %B %L %P',
        ),
        (
            "merge.state-json-smart.name",
            "Smart merge driver for state.json (dev-plugin)",
        ),
        (
            "merge.wbs-status-smart.driver",
            f'"{python_bin}" "{wbs_status_script}" %O %A %B %L %P',
        ),
        (
            "merge.wbs-status-smart.name",
            "Smart merge driver for wbs.md status lines (dev-plugin)",
        ),
    ]

    changed = 0
    noop = 0
    for key, val in drivers:
        if set_config_idempotent(worktree, key, val):
            changed += 1
        else:
            noop += 1
    return {"changed": changed, "noop": noop}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotent git rerere + merge driver setup for dev-plugin."
    )
    parser.add_argument(
        "--worktree",
        default=None,
        help="Git worktree directory (default: CWD)",
    )
    args = parser.parse_args()

    worktree = args.worktree or os.getcwd()

    # Verify git is available
    if not shutil.which("git"):
        print(
            "ERROR: git binary not found in PATH. "
            "Install git before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Verify target is a git repo
    r = subprocess.run(
        ["git", "-C", worktree, "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or r.stdout.strip() != "true":
        print(
            f"ERROR: {worktree!r} is not inside a git repository.",
            file=sys.stderr,
        )
        sys.exit(1)

    plugin_root = resolve_plugin_root()

    print(f"init-git-rerere: worktree={worktree!r}  plugin_root={str(plugin_root)!r}")

    print("\n[rerere]")
    rerere_result = configure_rerere(worktree, plugin_root)

    print("\n[merge drivers]")
    drivers_result = configure_merge_drivers(worktree, plugin_root)

    total_changed = rerere_result["changed"] + drivers_result["changed"]
    total_noop = rerere_result["noop"] + drivers_result["noop"]

    print(
        f"\nDone: {total_changed} changed, {total_noop} no-op "
        f"(rerere: {rerere_result['changed']}c/{rerere_result['noop']}n, "
        f"drivers: {drivers_result['changed']}c/{drivers_result['noop']}n)"
    )


if __name__ == "__main__":
    main()
