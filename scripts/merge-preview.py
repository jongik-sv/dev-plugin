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


def _run_git(args: list[str], cwd: pathlib.Path, check: bool = False) -> subprocess.CompletedProcess:
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
    result = _run_git(["status", "--porcelain"], cwd=repo_root)
    if result.returncode != 0 or result.stdout.strip():
        print(
            "ERROR: worktree has uncommitted changes — commit or stash before running merge-preview.",
            file=sys.stderr,
        )
        sys.exit(2)


def get_base_sha(remote: str, target: str, repo_root: pathlib.Path) -> str:
    """Return the merge-base SHA between HEAD and remote/target."""
    remote_ref = f"{remote}/{target}"
    result = _run_git(["merge-base", "HEAD", remote_ref], cwd=repo_root)
    if result.returncode != 0:
        # Fallback: try FETCH_HEAD
        result2 = _run_git(["merge-base", "HEAD", "FETCH_HEAD"], cwd=repo_root)
        if result2.returncode == 0:
            return result2.stdout.strip()
        return ""
    return result.stdout.strip()


def parse_conflicts(repo_root: pathlib.Path) -> list[dict]:
    """
    Parse unmerged (conflicted) files and their hunk lines from git diff output.
    Returns a list of {"file": str, "hunks": [str]}.

    Strategy: use `--name-only --diff-filter=U` to enumerate conflicted files,
    then `git diff --diff-filter=U` (combined diff, "diff --cc" headers) to get
    hunk content.  The two-pass approach is necessary because combined diffs use
    "diff --cc <file>" headers (not "diff --git a/... b/..."), so we cannot
    reliably extract file names from a single combined-diff call.
    """
    # Pass 1: enumerate conflicted file names
    name_result = _run_git(
        ["diff", "--name-only", "--diff-filter=U"],
        cwd=repo_root,
    )
    conflicted_files = [f for f in name_result.stdout.splitlines() if f.strip()]

    if not conflicted_files:
        return []

    # Pass 2: get full combined diff for hunk content
    diff_result = _run_git(["diff", "--diff-filter=U"], cwd=repo_root)

    # Build a lookup: file → hunk lines, keyed from "diff --cc <file>" headers
    hunk_map: dict[str, list[str]] = {}
    current_file: str | None = None
    current_hunks: list[str] = []

    for line in diff_result.stdout.splitlines():
        # Combined diff header: "diff --cc <file>"  (no "a/" / "b/" prefix)
        if line.startswith("diff --cc "):
            if current_file is not None:
                hunk_map[current_file] = current_hunks
            current_file = line[len("diff --cc "):]
            current_hunks = []
        elif current_file is not None:
            current_hunks.append(line)

    if current_file is not None:
        hunk_map[current_file] = current_hunks

    return [{"file": f, "hunks": hunk_map.get(f, [])} for f in conflicted_files]


def _is_up_to_date(merge_proc: subprocess.CompletedProcess) -> bool:
    """Return True if git merge reported that the branch is already up to date."""
    combined = (merge_proc.stdout + merge_proc.stderr).lower()
    return "already up to date" in combined


def simulate_merge(
    remote: str, target: str, repo_root: pathlib.Path
) -> tuple[bool, list[dict]]:
    """
    Simulate `git merge --no-commit --no-ff {remote}/{target}`.
    Always aborts via try/finally to ensure zero side-effects.
    Returns (clean: bool, conflicts: list[dict]).
    """
    # Fetch remote target first
    fetch = _run_git(["fetch", remote, target], cwd=repo_root)
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
    )

    merge_head = repo_root / ".git" / "MERGE_HEAD"
    try:
        if _is_up_to_date(merge_proc):
            return True, []

        if merge_proc.returncode == 0:
            # Staged clean merge — no conflicts
            return True, []

        # Non-zero, not "up to date" → conflicts present
        conflicts = parse_conflicts(repo_root)
        return False, conflicts
    finally:
        # Always restore worktree — abort if in merge state, else reset staged changes
        if merge_head.exists():
            _run_git(["merge", "--abort"], cwd=repo_root)
        else:
            _run_git(["reset", "--hard", "HEAD"], cwd=repo_root)


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
