"""TSK-06-03: scripts/merge-wbs-status.py 단위 테스트.

AC-28 + 설계 QA 체크리스트:
- test_merge_wbs_status_priority
- test_merge_wbs_status_non_status_conflict_preserved
- test_merge_wbs_status_pure_status_conflict_resolves
- test_merge_wbs_status_no_status_change
- test_merge_wbs_status_fallback_on_malformed_header
- test_merge_todo_union (git 내장 확인)
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "merge-wbs-status.py"


def _run_driver(
    base: pathlib.Path,
    ours: pathlib.Path,
    theirs: pathlib.Path,
    marker_size: str = "7",
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(base), str(ours), str(theirs), marker_size],
        capture_output=True,
        text=True,
    )


def _wbs_with_status(task_id: str, status: str, extra_lines: list[str] | None = None) -> str:
    extras = extra_lines or []
    parts = [
        "# WBS",
        "",
        f"### {task_id}: some title",
        "- category: infrastructure",
        "- domain: infra",
        f"- status: {status}",
        "- priority: high",
        *extras,
        "",  # trailing blank line
    ]
    return "\n".join(parts) + "\n"


class MergeWbsStatusTests(unittest.TestCase):
    def test_merge_wbs_status_priority(self) -> None:
        """동일 task 의 ours=[dd] theirs=[im] → 결과 [im]."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"
            base.write_text(_wbs_with_status("TSK-01-01", "[ ]"), encoding="utf-8")
            ours.write_text(_wbs_with_status("TSK-01-01", "[dd]"), encoding="utf-8")
            theirs.write_text(_wbs_with_status("TSK-01-01", "[im]"), encoding="utf-8")

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = ours.read_text(encoding="utf-8")
            self.assertIn("- status: [im]", merged)
            self.assertNotIn("- status: [dd]", merged)
            self.assertNotIn("- status: [ ]", merged)

    def test_merge_wbs_status_priority_xx_beats_ts(self) -> None:
        """[xx] > [ts]."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"
            base.write_text(_wbs_with_status("TSK-02-02", "[im]"), encoding="utf-8")
            ours.write_text(_wbs_with_status("TSK-02-02", "[ts]"), encoding="utf-8")
            theirs.write_text(_wbs_with_status("TSK-02-02", "[xx]"), encoding="utf-8")

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = ours.read_text(encoding="utf-8")
            self.assertIn("- status: [xx]", merged)

    def test_merge_wbs_status_non_status_conflict_preserved(self) -> None:
        """비-status 라인을 양쪽이 다르게 변경 → exit 1, OURS 미수정."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"
            base.write_text(
                _wbs_with_status("TSK-03-01", "[dd]", ["- note: base-note"]),
                encoding="utf-8",
            )
            ours.write_text(
                _wbs_with_status("TSK-03-01", "[im]", ["- note: ours-note"]),
                encoding="utf-8",
            )
            theirs.write_text(
                _wbs_with_status("TSK-03-01", "[im]", ["- note: theirs-note"]),
                encoding="utf-8",
            )
            ours_before = ours.read_bytes()

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 1)
            self.assertEqual(ours.read_bytes(), ours_before,
                             "OURS must not be modified on conflict fallback")

    def test_merge_wbs_status_pure_status_conflict_resolves(self) -> None:
        """양쪽이 같은 task status 만 다르게 → exit 0, 우선순위 결과."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"
            base.write_text(_wbs_with_status("TSK-04-01", "[dd]"), encoding="utf-8")
            ours.write_text(_wbs_with_status("TSK-04-01", "[im]"), encoding="utf-8")
            theirs.write_text(_wbs_with_status("TSK-04-01", "[ts]"), encoding="utf-8")

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = ours.read_text(encoding="utf-8")
            self.assertIn("- status: [ts]", merged)

    def test_merge_wbs_status_no_status_change(self) -> None:
        """양쪽이 status 는 안 바꾸고 다른 라인만 추가 → 3-way 라인 머지."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"
            base.write_text(
                _wbs_with_status("TSK-05-01", "[dd]"),
                encoding="utf-8",
            )
            ours.write_text(
                _wbs_with_status(
                    "TSK-05-01", "[dd]",
                    ["- tags: ours-tag"],
                ),
                encoding="utf-8",
            )
            theirs.write_text(
                _wbs_with_status(
                    "TSK-05-01", "[dd]",
                    ["- priority-note: theirs-add"],
                ),
                encoding="utf-8",
            )
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = ours.read_text(encoding="utf-8")
            self.assertIn("- status: [dd]", merged)
            # 양쪽 신규 라인 모두 보존 (non-conflict 인 추가만 라인들)
            self.assertIn("ours-tag", merged)
            self.assertIn("theirs-add", merged)

    def test_merge_wbs_status_two_tasks_independent(self) -> None:
        """서로 다른 task 의 status 변경은 각자 우선순위 머지 후 결합."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.md"
            ours = td_p / "ours.md"
            theirs = td_p / "theirs.md"

            def _two_task_wbs(t1: str, t2: str) -> str:
                return (
                    "# WBS\n"
                    "\n"
                    "### TSK-10-01: first\n"
                    "- category: backend\n"
                    f"- status: {t1}\n"
                    "- priority: high\n"
                    "\n"
                    "### TSK-10-02: second\n"
                    "- category: frontend\n"
                    f"- status: {t2}\n"
                    "- priority: medium\n"
                    "\n"
                )

            base.write_text(_two_task_wbs("[ ]", "[ ]"), encoding="utf-8")
            ours.write_text(_two_task_wbs("[dd]", "[ ]"), encoding="utf-8")
            theirs.write_text(_two_task_wbs("[ ]", "[im]"), encoding="utf-8")

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = ours.read_text(encoding="utf-8")
            self.assertIn("### TSK-10-01", merged)
            self.assertIn("### TSK-10-02", merged)
            # 앞 task 는 [dd], 뒤 task 는 [im]
            # 단순히 둘 다 merged 본문에 포함되는지 확인
            self.assertIn("- status: [dd]", merged)
            self.assertIn("- status: [im]", merged)


class GitTodoUnionTest(unittest.TestCase):
    """git 내장 union 드라이버가 docs/todo.md 에 대해 동작하는지 smoke test."""

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_merge_todo_union(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "repo"
            repo.mkdir()
            env = {**os.environ,
                   "HOME": str(repo / "_fake_home"),
                   "GIT_CONFIG_GLOBAL": "/dev/null",
                   "GIT_AUTHOR_NAME": "T",
                   "GIT_AUTHOR_EMAIL": "t@t.com",
                   "GIT_COMMITTER_NAME": "T",
                   "GIT_COMMITTER_EMAIL": "t@t.com"}
            (repo / "_fake_home").mkdir()

            def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
                return subprocess.run(["git", "-C", str(repo), *args],
                                      capture_output=True, text=True, env=env,
                                      check=check)

            run("init", "-b", "main")
            run("config", "user.email", "t@t.com")
            run("config", "user.name", "T")

            (repo / ".gitattributes").write_text(
                "docs/todo.md merge=union\n", encoding="utf-8")
            (repo / "docs").mkdir()
            (repo / "docs" / "todo.md").write_text(
                "line-a\n", encoding="utf-8")
            run("add", ".")
            run("commit", "-m", "base")

            run("checkout", "-b", "ours")
            (repo / "docs" / "todo.md").write_text(
                "line-a\nline-ours\n", encoding="utf-8")
            run("commit", "-am", "ours")

            run("checkout", "main")
            run("checkout", "-b", "theirs")
            (repo / "docs" / "todo.md").write_text(
                "line-a\nline-theirs\n", encoding="utf-8")
            run("commit", "-am", "theirs")

            run("checkout", "ours")
            merge = run("merge", "theirs", "--no-edit", check=False)
            self.assertEqual(merge.returncode, 0,
                             f"union merge should succeed, got stderr={merge.stderr}")
            merged = (repo / "docs" / "todo.md").read_text(encoding="utf-8")
            self.assertIn("line-ours", merged)
            self.assertIn("line-theirs", merged)


if __name__ == "__main__":
    unittest.main()
