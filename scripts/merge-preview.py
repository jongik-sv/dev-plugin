"""
merge-preview.py — Git merge conflict simulation (zero side-effect).

Usage:
    python3 merge-preview.py [--remote REMOTE] [--target TARGET]

Options:
    --remote REMOTE   Remote name (default: origin)
    --target TARGET   Target branch on remote (default: main)

Exit codes:
    0  Clean merge — JSON with clean=true
    1  Conflicts detected — JSON with clean=false, conflicts list
    2  Worktree is dirty (uncommitted changes) — exits before simulation

JSON stdout schema:
    {
        "clean": bool,
        "conflicts": [{"file": str, "hunks": [str]}],
        "base_sha": str
    }
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Dict, List, Tuple


def _run_git(args: List[str], cwd: pathlib.Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git sub-command and return the completed process."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def check_worktree_clean(repo_root: pathlib.Path) -> None:
    """Exit 2 with a stderr warning if the worktree has uncommitted changes."""
    result = _run_git(["status", "--porcelain"], cwd=repo_root, check=False)
    if result.returncode != 0 or result.stdout.strip():
        print(
            "ERROR: worktree has uncommitted changes — commit or stash before running merge-preview.",
            file=sys.stderr,
        )
        sys.exit(2)


def get_base_sha(remote: str, target: str, repo_root: pathlib.Path) -> str:
    """Return the merge-base SHA between HEAD and remote/target."""
    remote_ref = f"{remote}/{target}"
    result = _run_git(["merge-base", "HEAD", remote_ref], cwd=repo_root, check=False)
    if result.returncode != 0:
        # Fallback: try FETCH_HEAD
        result2 = _run_git(["merge-base", "HEAD", "FETCH_HEAD"], cwd=repo_root, check=False)
        if result2.returncode == 0:
            return result2.stdout.strip()
        return ""
    return result.stdout.strip()


def parse_conflicts(repo_root: pathlib.Path) -> List[Dict]:
    """
    Parse unmerged (conflicted) files and their hunk lines from git diff output.
    Returns a list of {"file": str, "hunks": [str]}.
    """
    # Get list of conflicted files
    unmerged = _run_git(
        ["diff", "--name-only", "--diff-filter=U"],
        cwd=repo_root,
        check=False,
    )
    conflicted_files = [f for f in unmerged.stdout.splitlines() if f.strip()]

    if not conflicted_files:
        return []

    # Get full diff for unmerged files to extract hunk lines
    diff_result = _run_git(
        ["diff", "--diff-filter=U"],
        cwd=repo_root,
        check=False,
    )

    # Parse diff output per file
    conflicts = []
    current_file = None
    current_hunks: List[str] = []

    for line in diff_result.stdout.splitlines():
        if line.startswith("diff --git "):
            if current_file is not None:
                conflicts.append({"file": current_file, "hunks": current_hunks})
            # Extract file name from "diff --git a/path b/path"
            parts = line.split(" b/", 1)
            current_file = parts[1] if len(parts) == 2 else line
            current_hunks = []
        elif current_file is not None:
            current_hunks.append(line)

    if current_file is not None:
        conflicts.append({"file": current_file, "hunks": current_hunks})

    # For files that appeared in --name-only but not in diff (edge case), add them
    listed = {c["file"] for c in conflicts}
    for f in conflicted_files:
        if f not in listed:
            conflicts.append({"file": f, "hunks": []})

    return conflicts


def simulate_merge(
    remote: str, target: str, repo_root: pathlib.Path
) -> Tuple[bool, List[Dict]]:
    """
    Simulate `git merge --no-commit --no-ff {remote}/{target}`.
    Always aborts via try/finally to ensure zero side-effects.
    Returns (clean: bool, conflicts: list[dict]).
    """
    # Fetch remote target first
    fetch = _run_git(["fetch", remote, target], cwd=repo_root, check=False)
    if fetch.returncode != 0:
        print(
            f"ERROR: git fetch {remote} {target} failed:\n{fetch.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)

    remote_ref = f"{remote}/{target}"
    merge_proc = _run_git(
        ["merge", "--no-commit", "--no-ff", remote_ref],
        cwd=repo_root,
        check=False,
    )

    merge_head = repo_root / ".git" / "MERGE_HEAD"
    try:
        # Determine outcome
        # A clean fast-forward-able merge exits 0 and creates MERGE_HEAD briefly,
        # but --no-commit keeps it staged.  A conflict also exits non-zero.
        if merge_proc.returncode == 0:
            # Check if there are any unmerged files (shouldn't be, but be defensive)
            unmerged = _run_git(
                ["diff", "--name-only", "--diff-filter=U"],
                cwd=repo_root,
                check=False,
            )
            if unmerged.stdout.strip():
                conflicts = parse_conflicts(repo_root)
                return False, conflicts
            return True, []
        else:
            # Non-zero: could be conflict (exit 1) or already up-to-date (handled above)
            # Check "Already up to date" case
            if "Already up to date" in merge_proc.stdout or "up to date" in merge_proc.stdout.lower():
                return True, []
            conflicts = parse_conflicts(repo_root)
            return False, conflicts
    finally:
        # Always abort to restore worktree — safe even if merge succeeded (--no-commit)
        if merge_head.exists():
            _run_git(["merge", "--abort"], cwd=repo_root, check=False)
        else:
            # Clean merge staged changes — reset HEAD to clean state
            _run_git(["reset", "--hard", "HEAD"], cwd=repo_root, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate a git merge and report conflicts as JSON."
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote name (default: origin)",
    )
    parser.add_argument(
        "--target",
        default="main",
        help="Target branch on remote (default: main)",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path.cwd()

    # Step 1: ensure worktree is clean
    check_worktree_clean(repo_root)

    # Step 2: get base SHA
    base_sha = get_base_sha(args.remote, args.target, repo_root)

    # Step 3: simulate merge (always aborts in finally)
    clean, conflicts = simulate_merge(args.remote, args.target, repo_root)

    # Step 4: output JSON
    output = {
        "clean": clean,
        "conflicts": conflicts,
        "base_sha": base_sha,
    }
    print(json.dumps(output))

    sys.exit(0 if clean else 1)


if __name__ == "__main__":
    main()
