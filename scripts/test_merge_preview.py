"""
TSK-06-01: scripts/merge-preview.py 단위 테스트
- test_merge_preview_clean_merge
- test_merge_preview_detects_conflicts
- test_merge_preview_dirty_worktree_exits_2
- test_dev_build_skill_contains_merge_preview_step

TSK-04-01: scripts/merge-preview.py --output 플래그 단위 테스트
- test_merge_preview_output_flag
- test_merge_preview_stdout_still_works
- test_merge_preview_atomic_rename
- test_merge_preview_output_dir_auto_create
- test_tdd_prompt_contains_merge_preview_hook (count == 1)
- test_tdd_prompt_contains_or_true
- test_tdd_prompt_contains_no_read_instruction
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import threading
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


def _make_clean_repo(tmp: pathlib.Path) -> pathlib.Path:
    """Create origin+local repos where merging is clean (no conflicts)."""
    origin = tmp / "origin"
    origin.mkdir()
    _git(["init", "-b", "main"], cwd=origin)
    _git(["config", "user.email", "test@example.com"], cwd=origin)
    _git(["config", "user.name", "Test"], cwd=origin)
    (origin / "file.txt").write_text("line1\n")
    _git(["add", "."], cwd=origin)
    _git(["commit", "-m", "init"], cwd=origin)

    local = tmp / "local"
    _git(["clone", str(origin), str(local)], cwd=tmp)
    _git(["config", "user.email", "test@example.com"], cwd=local)
    _git(["config", "user.name", "Test"], cwd=local)

    # Origin adds a new file — clean merge
    (origin / "newfile.txt").write_text("new content\n")
    _git(["add", "."], cwd=origin)
    _git(["commit", "-m", "add newfile"], cwd=origin)

    return local


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


class TestMergePreviewOutputFlag(unittest.TestCase):
    """test_merge_preview_output_flag: --output flag writes JSON to file."""

    def test_merge_preview_output_flag(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_clean_repo(tmp)

            output_file = tmp / "preview.json"

            result = _run_script(
                local,
                ["--remote", "origin", "--target", "main", "--output", str(output_file)],
            )

            # Clean merge → exit 0
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0, got {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}",
            )

            # Output file must exist
            self.assertTrue(
                output_file.exists(),
                f"Output file not created at {output_file}",
            )

            # File content must be valid JSON with expected schema
            file_data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertIn("clean", file_data)
            self.assertIn("conflicts", file_data)
            self.assertIn("base_sha", file_data)
            self.assertIsInstance(file_data["clean"], bool)
            self.assertIsInstance(file_data["conflicts"], list)
            self.assertIsInstance(file_data["base_sha"], str)


class TestMergePreviewStdoutStillWorks(unittest.TestCase):
    """test_merge_preview_stdout_still_works: stdout JSON output is preserved with and without --output."""

    def test_stdout_without_output_flag(self):
        """기존 방식(--output 없음): stdout에 유효 JSON 출력."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_clean_repo(tmp)

            result = _run_script(local, ["--remote", "origin", "--target", "main"])

            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertIn("clean", data)
            self.assertIn("conflicts", data)
            self.assertIn("base_sha", data)

    def test_stdout_with_output_flag(self):
        """--output 지정 시에도 stdout에 동일 JSON 출력 (하위 호환)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_clean_repo(tmp)
            output_file = tmp / "preview.json"

            result = _run_script(
                local,
                ["--remote", "origin", "--target", "main", "--output", str(output_file)],
            )

            self.assertEqual(result.returncode, 0)
            stdout_data = json.loads(result.stdout)
            file_data = json.loads(output_file.read_text(encoding="utf-8"))

            # stdout and file must contain equivalent data
            self.assertEqual(stdout_data["clean"], file_data["clean"])
            self.assertEqual(stdout_data["conflicts"], file_data["conflicts"])
            self.assertEqual(stdout_data["base_sha"], file_data["base_sha"])


class TestMergePreviewAtomicRename(unittest.TestCase):
    """test_merge_preview_atomic_rename: write_output_file uses atomic rename (concurrent-write safe)."""

    @classmethod
    def _load_module(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("merge_preview", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_single_write(self):
        """기본 단일 write: 파일이 생성되고 내용이 일치한다."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp_str:
            output_file = pathlib.Path(tmp_str) / "test-output.json"
            payload = {"clean": True, "conflicts": [], "base_sha": "abc123"}

            mod.write_output_file(payload, output_file)

            self.assertTrue(output_file.exists())
            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(data, payload)

    def test_merge_preview_atomic_rename(self):
        """동시 write: 최종 파일이 항상 유효한 JSON (부분 쓰기 없음)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp_str:
            output_file = pathlib.Path(tmp_str) / "concurrent" / "preview.json"
            payloads = [
                {"clean": True, "conflicts": [], "base_sha": f"sha{i:040d}"}
                for i in range(10)
            ]
            errors: list[Exception] = []

            def write_one(payload: dict) -> None:
                try:
                    mod.write_output_file(payload, output_file)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=write_one, args=(p,)) for p in payloads]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"write_output_file raised errors: {errors}")
            self.assertTrue(output_file.exists(), "Output file missing after concurrent writes")
            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertIn("clean", data)
            self.assertIn("base_sha", data)


class TestMergePreviewOutputDirAutoCreate(unittest.TestCase):
    """test_merge_preview_output_dir_auto_create: --output auto-creates missing parent directories."""

    def test_merge_preview_output_dir_auto_create(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            local = _make_clean_repo(tmp)

            # Deeply nested path whose parents do not exist yet
            output_file = tmp / "a" / "b" / "c" / "preview.json"
            self.assertFalse(output_file.parent.exists(), "Test pre-condition: parent must not exist")

            result = _run_script(
                local,
                ["--remote", "origin", "--target", "main", "--output", str(output_file)],
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0, got {result.returncode}.\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertTrue(
                output_file.exists(),
                f"Output file not created at {output_file}; parent dirs should be auto-created",
            )
            file_data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertIn("clean", file_data)


class TestMergePreviewHookInTemplate(unittest.TestCase):
    """test_tdd_prompt_contains_merge_preview_hook: tdd-prompt-template.md contains --output hook exactly once."""

    def _read_template(self) -> str:
        self.assertTrue(
            SKILL_TEMPLATE.exists(),
            f"tdd-prompt-template.md not found at {SKILL_TEMPLATE}",
        )
        return SKILL_TEMPLATE.read_text(encoding="utf-8")

    def test_tdd_prompt_contains_merge_preview_hook(self):
        content = self._read_template()
        count = content.count("merge-preview.py --output")
        self.assertEqual(
            count,
            1,
            f"Expected 'merge-preview.py --output' to appear exactly once, but found {count} occurrences",
        )

    def test_tdd_prompt_contains_or_true(self):
        """삽입된 블록에 || true가 포함되어야 한다."""
        content = self._read_template()
        idx = content.find("merge-preview.py --output")
        self.assertGreater(idx, -1, "merge-preview.py --output not found")
        # Check within 500 chars after the hook for || true
        surrounding = content[idx: idx + 500]
        self.assertIn(
            "|| true",
            surrounding,
            "|| true must appear near the merge-preview --output hook",
        )

    def test_tdd_prompt_contains_no_read_instruction(self):
        """삽입된 블록에 LLM 해석 금지 문구가 포함되어야 한다."""
        content = self._read_template()
        idx = content.find("merge-preview.py --output")
        self.assertGreater(idx, -1, "merge-preview.py --output not found")
        # Check within 300 chars before and 500 after the hook
        surrounding = content[max(0, idx - 300): idx + 500]
        has_no_read = (
            "읽지 마시오" in surrounding
            or "결과를 읽지" in surrounding
            or "읽거나 해석하지 마시오" in surrounding
            or "do not read" in surrounding.lower()
            or "must not read" in surrounding.lower()
        )
        self.assertTrue(
            has_no_read,
            f"No 'do not read' instruction found near the hook.\nContext: {surrounding!r}",
        )


if __name__ == "__main__":
    unittest.main()
