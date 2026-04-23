"""
TSK-06-01: scripts/merge-preview.py 단위 테스트
- test_merge_preview_clean_merge
- test_merge_preview_detects_conflicts
- test_merge_preview_dirty_worktree_exits_2
- test_dev_build_skill_contains_merge_preview_step
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "merge-preview.py"
SKILL_TEMPLATE = (
    REPO_ROOT
    / "skills"
    / "dev-build"
    / "references"
    / "tdd-prompt-template.md"
)


def _git(args: list[str], cwd: pathlib.Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def _make_conflict_setup(tmp: pathlib.Path) -> pathlib.Path:
    """
    Create two repos (origin + local) where merging origin/main into local/main
    would produce a conflict on file.txt.
    Returns the local repo path.
    """
    # origin
    origin = tmp / "origin"
    origin.mkdir()
    _git(["init", "-b", "main"], cwd=origin)
    _git(["config", "user.email", "test@example.com"], cwd=origin)
    _git(["config", "user.name", "Test"], cwd=origin)
    (origin / "file.txt").write_text("shared base\n")
    _git(["add", "."], cwd=origin)
    _git(["commit", "-m", "init"], cwd=origin)

    # local: clone from origin
    local = tmp / "local"
    _git(["clone", str(origin), str(local)], cwd=tmp)
    _git(["config", "user.email", "test@example.com"], cwd=local)
    _git(["config", "user.name", "Test"], cwd=local)

    # diverge: origin modifies file.txt
    (origin / "file.txt").write_text("origin change\n")
    _git(["add", "."], cwd=origin)
    _git(["commit", "-m", "origin change"], cwd=origin)

    # local also modifies file.txt → conflict
    (local / "file.txt").write_text("local change\n")
    _git(["add", "."], cwd=local)
    _git(["commit", "-m", "local change"], cwd=local)

    return local


def _run_script(
    repo: pathlib.Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)] + (extra_args or [])
    return subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


class TestMergePreviewCleanMerge(unittest.TestCase):
    """test_merge_preview_clean_merge: clean merge → exit 0, JSON clean=true."""

    def test_merge_preview_clean_merge(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)

            # Set up origin and local repos
            origin = tmp / "origin"
            origin.mkdir()
            _git(["init", "-b", "main"], cwd=origin)
            _git(["config", "user.email", "test@example.com"], cwd=origin)
            _git(["config", "user.name", "Test"], cwd=origin)
            (origin / "file.txt").write_text("line1\n")
            _git(["add", "."], cwd=origin)
            _git(["commit", "-m", "init"], cwd=origin)

            # local: clone from origin (no divergence yet)
            local = tmp / "local"
            _git(["clone", str(origin), str(local)], cwd=tmp)
            _git(["config", "user.email", "test@example.com"], cwd=local)
            _git(["config", "user.name", "Test"], cwd=local)

            # Add a new file in origin only → clean merge (no conflict)
            (origin / "newfile.txt").write_text("new content\n")
            _git(["add", "."], cwd=origin)
            _git(["commit", "-m", "add newfile"], cwd=origin)

            result = _run_script(
                local, ["--remote", "origin", "--target", "main"]
            )

            # Must exit 0
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 for clean merge, got {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}",
            )

            # stdout must be valid JSON
            data = json.loads(result.stdout)
            self.assertTrue(data["clean"], f"Expected clean=true, got: {data}")
            self.assertEqual(data["conflicts"], [], f"Expected empty conflicts, got: {data}")
            self.assertIn("base_sha", data)
            self.assertIsInstance(data["base_sha"], str)
            self.assertGreater(len(data["base_sha"]), 0)

            # After script, worktree must be clean (no MERGE_HEAD left behind)
            merge_head = local / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head.exists(),
                "MERGE_HEAD should not exist after clean simulation",
            )


class TestMergePreviewDetectsConflicts(unittest.TestCase):
    """test_merge_preview_detects_conflicts: conflict → exit 1, clean=false, conflicts non-empty."""

    def test_merge_preview_detects_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_conflict_setup(tmp)

            result = _run_script(
                local, ["--remote", "origin", "--target", "main"]
            )

            # Must exit 1
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 for conflicts, got {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}",
            )

            data = json.loads(result.stdout)
            self.assertFalse(data["clean"], f"Expected clean=false, got: {data}")
            self.assertGreater(
                len(data["conflicts"]),
                0,
                f"Expected at least one conflict, got: {data}",
            )
            # Each conflict entry must have "file" key
            for entry in data["conflicts"]:
                self.assertIn("file", entry, f"Conflict entry missing 'file': {entry}")

            # After script, worktree must be clean (abort must have run)
            merge_head = local / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head.exists(),
                "MERGE_HEAD should not exist after abort — worktree contaminated",
            )
            status = _git(["status", "--porcelain"], cwd=local)
            self.assertEqual(
                status.stdout.strip(),
                "",
                f"Worktree dirty after simulation: {status.stdout}",
            )


class TestMergePreviewDirtyWorktreeExits2(unittest.TestCase):
    """test_merge_preview_dirty_worktree_exits_2: uncommitted changes → exit 2."""

    def test_merge_preview_dirty_worktree_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_conflict_setup(tmp)

            # Introduce an uncommitted change
            (local / "dirty.txt").write_text("uncommitted\n")

            result = _run_script(
                local, ["--remote", "origin", "--target", "main"]
            )

            self.assertEqual(
                result.returncode,
                2,
                f"Expected exit 2 for dirty worktree, got {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            # stderr must contain a warning
            self.assertGreater(
                len(result.stderr.strip()),
                0,
                "Expected stderr warning for dirty worktree",
            )


class TestDevBuildSkillContainsMergePreviewStep(unittest.TestCase):
    """test_dev_build_skill_contains_merge_preview_step: tdd-prompt-template.md contains merge-preview.py."""

    def test_dev_build_skill_contains_merge_preview_step(self):
        self.assertTrue(
            SKILL_TEMPLATE.exists(),
            f"tdd-prompt-template.md not found at {SKILL_TEMPLATE}",
        )
        content = SKILL_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(
            "merge-preview.py",
            content,
            "tdd-prompt-template.md must reference 'merge-preview.py' (AC-29)",
        )


if __name__ == "__main__":
    unittest.main()
