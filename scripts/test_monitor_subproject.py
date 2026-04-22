"""Unit tests for TSK-00-03: discover_subprojects / _filter_by_subproject.

실행: python3 -m unittest scripts/test_monitor_subproject.py -v
또는: python3 -m unittest discover -s scripts -p "test_monitor_subproject.py" -v
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


# monitor-server.py는 파일명에 하이픈이 있어 일반 import 불가 → importlib로 로드
_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

discover_subprojects = monitor_server.discover_subprojects
_filter_by_subproject = monitor_server._filter_by_subproject


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(text)


class TestDiscoverSubprojectsMulti(unittest.TestCase):
    """test_discover_subprojects_multi — docs/p1/wbs.md + docs/p2/wbs.md 존재 시 ['p1', 'p2'] 반환."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-multi-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_discover_subprojects_multi(self) -> None:
        docs = self.tmp
        # p1, p2 서브프로젝트 — 각 child 디렉터리에 wbs.md 배치
        _write(docs / "p1" / "wbs.md", "# WBS p1\n")
        _write(docs / "p2" / "wbs.md", "# WBS p2\n")

        result = discover_subprojects(docs)

        self.assertEqual(result, ["p1", "p2"])

    def test_discover_subprojects_multi_sorted(self) -> None:
        """정렬 순서 보장 — b, a 순으로 생성해도 ['a', 'b'] 반환."""
        docs = self.tmp
        _write(docs / "b_sp" / "wbs.md", "# WBS b\n")
        _write(docs / "a_sp" / "wbs.md", "# WBS a\n")

        result = discover_subprojects(docs)

        self.assertEqual(result, ["a_sp", "b_sp"])

    def test_is_multi_mode_true(self) -> None:
        """is_multi_mode = len(discover_subprojects(docs_dir)) > 0 → True."""
        docs = self.tmp
        _write(docs / "proj1" / "wbs.md", "# WBS proj1\n")

        is_multi_mode = len(discover_subprojects(docs)) > 0

        self.assertTrue(is_multi_mode)


class TestDiscoverSubprojectsLegacy(unittest.TestCase):
    """test_discover_subprojects_legacy — docs/wbs.md만 있고 child에 wbs.md 없을 때 [] 반환."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-legacy-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_discover_subprojects_legacy(self) -> None:
        docs = self.tmp
        # 루트에만 wbs.md — child 디렉터리에는 없음
        _write(docs / "wbs.md", "# WBS root\n")
        # child 디렉터리 존재하되 wbs.md 없음
        (docs / "some_child").mkdir(exist_ok=True)

        result = discover_subprojects(docs)

        self.assertEqual(result, [])

    def test_discover_subprojects_empty_docs(self) -> None:
        """child 디렉터리 자체가 없으면 [] 반환."""
        docs = self.tmp  # 빈 디렉터리

        result = discover_subprojects(docs)

        self.assertEqual(result, [])

    def test_is_multi_mode_false(self) -> None:
        """is_multi_mode = len(discover_subprojects(docs_dir)) > 0 → False (레거시)."""
        docs = self.tmp
        _write(docs / "wbs.md", "# WBS root\n")

        is_multi_mode = len(discover_subprojects(docs)) > 0

        self.assertFalse(is_multi_mode)


class TestDiscoverSubprojectsIgnoresDirsWithoutWbs(unittest.TestCase):
    """test_discover_subprojects_ignores_dirs_without_wbs — tasks/, features/ 등 wbs.md 없는 디렉터리 제외."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-ignore-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_discover_subprojects_ignores_dirs_without_wbs(self) -> None:
        docs = self.tmp
        # wbs.md 없는 표준 docs 하위 디렉터리
        (docs / "tasks").mkdir(exist_ok=True)
        (docs / "features").mkdir(exist_ok=True)
        (docs / "tasks" / "TSK-01-01").mkdir(parents=True, exist_ok=True)
        # 실제 서브프로젝트 하나
        _write(docs / "sub1" / "wbs.md", "# WBS sub1\n")

        result = discover_subprojects(docs)

        self.assertNotIn("tasks", result)
        self.assertNotIn("features", result)
        self.assertIn("sub1", result)

    def test_discover_subprojects_nonexistent_docs_dir(self) -> None:
        """존재하지 않는 docs_dir → [] 반환 (예외 없음)."""
        nonexistent = self.tmp / "does_not_exist"

        result = discover_subprojects(nonexistent)

        self.assertEqual(result, [])

    def test_discover_subprojects_file_not_dir_child(self) -> None:
        """child가 디렉터리가 아닌 파일이면 건너뜀."""
        docs = self.tmp
        # child로 파일 배치 (디렉터리 아님)
        _write(docs / "readme.md", "readme\n")
        _write(docs / "real_sp" / "wbs.md", "# WBS\n")

        result = discover_subprojects(docs)

        self.assertEqual(result, ["real_sp"])


class TestFilterBySubprojectSignals(unittest.TestCase):
    """test_filter_by_subproject_signals — signal scope 기반 필터링."""

    def _make_state(self, signals, panes=None) -> dict:
        return {
            "signals": signals,
            "tmux_panes": panes,
        }

    def _make_signal(self, scope: str) -> dict:
        return {"scope": scope, "name": "TSK-01.done", "kind": "done"}

    def test_filter_by_subproject_signals(self) -> None:
        """scope='proj-a-billing' 통과, 'proj-a-reporting' 제외."""
        state = self._make_state([
            self._make_signal("proj-a-billing"),
            self._make_signal("proj-a-reporting"),
            self._make_signal("proj-a-billing-sub"),
        ])

        result = _filter_by_subproject(state, "billing", "proj-a")

        scopes = [s["scope"] for s in result["signals"]]
        self.assertIn("proj-a-billing", scopes)
        self.assertIn("proj-a-billing-sub", scopes)
        self.assertNotIn("proj-a-reporting", scopes)

    def test_filter_by_subproject_signals_exact_match(self) -> None:
        """scope가 정확히 '{project_name}-{sp}'이면 통과."""
        state = self._make_state([
            self._make_signal("myproj-alpha"),
        ])

        result = _filter_by_subproject(state, "alpha", "myproj")

        self.assertEqual(len(result["signals"]), 1)
        self.assertEqual(result["signals"][0]["scope"], "myproj-alpha")

    def test_filter_by_subproject_signals_prefix_match(self) -> None:
        """scope가 '{project_name}-{sp}-*' 패턴이면 통과."""
        state = self._make_state([
            self._make_signal("myproj-alpha-extra"),
            self._make_signal("myproj-alphaX"),  # 이건 prefix 매칭 아님
        ])

        result = _filter_by_subproject(state, "alpha", "myproj")

        scopes = [s["scope"] for s in result["signals"]]
        self.assertIn("myproj-alpha-extra", scopes)
        self.assertNotIn("myproj-alphaX", scopes)

    def test_filter_by_subproject_no_matching_signals(self) -> None:
        """일치하는 signal 없으면 빈 리스트 반환."""
        state = self._make_state([
            self._make_signal("other-proj-billing"),
        ])

        result = _filter_by_subproject(state, "billing", "proj-a")

        self.assertEqual(result["signals"], [])


class TestFilterBySubprojectPanesByWindow(unittest.TestCase):
    """test_filter_by_subproject_panes_by_window — pane window_name 기반 필터링."""

    def _make_pane(self, window_name: str, cwd: str = "/home/user") -> dict:
        return {
            "window_name": window_name,
            "pane_current_path": cwd,
            "pane_id": "%1",
        }

    def _make_state(self, panes, signals=None) -> dict:
        return {
            "signals": signals or [],
            "tmux_panes": panes,
        }

    def test_filter_by_subproject_panes_by_window(self) -> None:
        """window_name='WP-01-billing' (suffix '-billing') 통과, 'WP-01-reporting' 제외."""
        state = self._make_state([
            self._make_pane("WP-01-billing"),
            self._make_pane("WP-01-reporting"),
        ])

        result = _filter_by_subproject(state, "billing", "myproj")

        names = [p["window_name"] for p in result["tmux_panes"]]
        self.assertIn("WP-01-billing", names)
        self.assertNotIn("WP-01-reporting", names)

    def test_filter_by_subproject_panes_contains_sp_infix(self) -> None:
        """window_name에 '-{sp}-' 포함이면 통과 (예: 'WP-01-billing-extra')."""
        state = self._make_state([
            self._make_pane("WP-01-billing-extra"),
            self._make_pane("WP-01-other"),
        ])

        result = _filter_by_subproject(state, "billing", "myproj")

        names = [p["window_name"] for p in result["tmux_panes"]]
        self.assertIn("WP-01-billing-extra", names)
        self.assertNotIn("WP-01-other", names)

    def test_filter_by_subproject_panes_by_cwd(self) -> None:
        """pane_current_path에 '/{sp}/' 포함이면 통과."""
        state = self._make_state([
            self._make_pane("any-window", cwd="/home/user/project/billing/src"),
            self._make_pane("other-window", cwd="/home/user/project/reporting/src"),
        ])

        result = _filter_by_subproject(state, "billing", "myproj")

        names = [p["window_name"] for p in result["tmux_panes"]]
        self.assertIn("any-window", names)
        self.assertNotIn("other-window", names)

    def test_filter_by_subproject_panes_none_preserved(self) -> None:
        """tmux_panes가 None이면 None 그대로 유지 (tmux 미설치 환경)."""
        state = {
            "signals": [],
            "tmux_panes": None,
        }

        result = _filter_by_subproject(state, "billing", "myproj")

        self.assertIsNone(result["tmux_panes"])

    def test_filter_by_subproject_panes_empty_list(self) -> None:
        """tmux_panes가 빈 리스트면 빈 리스트 반환."""
        state = self._make_state([])

        result = _filter_by_subproject(state, "billing", "myproj")

        self.assertEqual(result["tmux_panes"], [])


if __name__ == "__main__":
    unittest.main()
