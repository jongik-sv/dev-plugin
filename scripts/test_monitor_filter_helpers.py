"""Unit tests for _filter_panes_by_project / _filter_signals_by_project (TSK-00-02).

QA 체크리스트 기반 — design.md §QA 체크리스트 전항목 포함.

실행: pytest -q scripts/test_monitor_filter_helpers.py
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Module loader (동일 프로젝트 내 다른 test_monitor_*.py와 동일 패턴)
# ---------------------------------------------------------------------------

def _load_monitor_server():
    here = Path(__file__).resolve().parent
    src = here / "monitor-server.py"
    spec = importlib.util.spec_from_file_location("monitor_server_tsk0002", src)
    module = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_tsk0002"] = module
    spec.loader.exec_module(module)
    return module


MS = _load_monitor_server()


# ---------------------------------------------------------------------------
# Helpers to build PaneInfo / SignalEntry stubs
# ---------------------------------------------------------------------------

def _make_pane(window_name="win", window_id="@1", pane_id="%0",
               pane_index=0, pane_current_path="/tmp",
               pane_current_command="zsh", pane_pid=1234, is_active=False):
    return MS.PaneInfo(
        window_name=window_name,
        window_id=window_id,
        pane_id=pane_id,
        pane_index=pane_index,
        pane_current_path=pane_current_path,
        pane_current_command=pane_current_command,
        pane_pid=pane_pid,
        is_active=is_active,
    )


def _make_signal(scope="shared", name="TSK-01.done", kind="done",
                 task_id="TSK-01", mtime="2026-01-01T00:00:00+00:00"):
    return MS.SignalEntry(
        name=name,
        kind=kind,
        task_id=task_id,
        mtime=mtime,
        scope=scope,
    )


# ---------------------------------------------------------------------------
# Tests: _filter_panes_by_project
# ---------------------------------------------------------------------------

class TestFilterPanesByProjectRootStartswith(unittest.TestCase):
    """design.md QA: test_filter_panes_by_project_root_startswith"""

    def test_pane_in_subdir_included(self):
        """pane_current_path=/proj/a/src, project_root=/proj/a → included."""
        pane = _make_pane(pane_current_path="/proj/a/src")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertIn(pane, result)

    def test_pane_exact_root_included(self):
        """pane_current_path=/proj/a (정확 일치) → included."""
        pane = _make_pane(pane_current_path="/proj/a")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertIn(pane, result)

    def test_pane_outside_root_excluded(self):
        """pane_current_path=/other/path → excluded."""
        pane = _make_pane(pane_current_path="/other/path")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertNotIn(pane, result)

    def test_prefix_false_positive_prevention(self):
        """pane_current_path=/proj/alpha/src, project_root=/proj/a → excluded.

        단순 startswith("/proj/a") 오탐 방지 — root + os.sep 비교 필수.
        """
        import os
        pane = _make_pane(pane_current_path="/proj/alpha/src")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertNotIn(pane, result)

    def test_trailing_sep_on_root_normalized(self):
        """project_root=/proj/a/ (trailing sep) — rstrip으로 정규화 후 매칭."""
        pane = _make_pane(pane_current_path="/proj/a/src")
        result = MS._filter_panes_by_project([pane], "/proj/a/", "myproj")
        self.assertIn(pane, result)


class TestFilterPanesByProjectWindowNameMatch(unittest.TestCase):
    """design.md QA: test_filter_panes_by_project_window_name_match"""

    def test_window_name_wp_pattern_included(self):
        """window_name=WP-01-myproj, project_name=myproj → included (cwd 무관)."""
        pane = _make_pane(window_name="WP-01-myproj", pane_current_path="/unrelated/dir")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertIn(pane, result)

    def test_window_name_wrong_project_excluded(self):
        """window_name=WP-01-otherproj, project_name=myproj → excluded."""
        pane = _make_pane(window_name="WP-01-otherproj", pane_current_path="/unrelated/dir")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertNotIn(pane, result)

    def test_window_name_no_wp_prefix_excluded(self):
        """window_name이 WP-로 시작하지 않으면 window_name 경로로 통과하지 않는다."""
        pane = _make_pane(window_name="myproj-worker", pane_current_path="/unrelated/dir")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertNotIn(pane, result)

    def test_window_name_wp_multi_segment(self):
        """window_name=WP-03-04-myproj (multi-segment WP ID) → included."""
        pane = _make_pane(window_name="WP-03-04-myproj", pane_current_path="/unrelated")
        result = MS._filter_panes_by_project([pane], "/proj/a", "myproj")
        self.assertIn(pane, result)


class TestFilterPanesByProjectEdgeCases(unittest.TestCase):
    """design.md QA: 엣지 케이스"""

    def test_none_input_returns_none(self):
        """panes=None → None 반환 (tmux 미설치 신호 보존)."""
        result = MS._filter_panes_by_project(None, "/proj/a", "myproj")
        self.assertIsNone(result)

    def test_empty_list_returns_empty(self):
        """빈 리스트 → 빈 리스트 반환."""
        result = MS._filter_panes_by_project([], "/proj/a", "myproj")
        self.assertEqual(result, [])

    def test_multiple_panes_mixed(self):
        """여러 pane 중 project 귀속 pane만 반환."""
        inside = _make_pane(pane_id="%0", pane_current_path="/proj/a/src")
        outside = _make_pane(pane_id="%1", pane_current_path="/other")
        wp_pane = _make_pane(pane_id="%2", window_name="WP-01-myproj", pane_current_path="/anywhere")
        result = MS._filter_panes_by_project([inside, outside, wp_pane], "/proj/a", "myproj")
        self.assertIn(inside, result)
        self.assertNotIn(outside, result)
        self.assertIn(wp_pane, result)
        self.assertEqual(len(result), 2)

    def test_returns_new_list_not_same_object(self):
        """원본 리스트를 변경하지 않고 새 리스트를 반환."""
        panes = [_make_pane(pane_current_path="/proj/a/src")]
        result = MS._filter_panes_by_project(panes, "/proj/a", "myproj")
        self.assertIsNot(result, panes)


# ---------------------------------------------------------------------------
# Tests: _filter_signals_by_project
# ---------------------------------------------------------------------------

class TestFilterSignalsByProject(unittest.TestCase):
    """design.md QA: test_filter_signals_by_project"""

    def test_exact_project_name_included(self):
        """scope=myproj, project_name=myproj → 통과."""
        sig = _make_signal(scope="myproj")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertIn(sig, result)

    def test_subproject_scope_included(self):
        """scope=myproj-billing, project_name=myproj → 통과 (서브프로젝트)."""
        sig = _make_signal(scope="myproj-billing")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertIn(sig, result)

    def test_deeper_subproject_included(self):
        """scope=proj-a-billing-eu, project_name=proj-a → 통과."""
        sig = _make_signal(scope="proj-a-billing-eu")
        result = MS._filter_signals_by_project([sig], "proj-a")
        self.assertIn(sig, result)

    def test_other_project_excluded(self):
        """scope=otherproj, project_name=myproj → 제외."""
        sig = _make_signal(scope="otherproj")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertNotIn(sig, result)

    def test_prefix_false_positive_prevention(self):
        """scope=myproj2, project_name=myproj → 제외 (startswith(name+'-') 검사)."""
        sig = _make_signal(scope="myproj2")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertNotIn(sig, result)

    def test_empty_scope_excluded(self):
        """scope="" → 제외."""
        sig = _make_signal(scope="")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertNotIn(sig, result)

    def test_empty_list_returns_empty(self):
        """빈 리스트 → 빈 리스트 반환."""
        result = MS._filter_signals_by_project([], "myproj")
        self.assertEqual(result, [])

    def test_multiple_signals_mixed(self):
        """여러 signal 중 project 귀속만 반환."""
        s_same = _make_signal(scope="myproj", task_id="TSK-01")
        s_sub = _make_signal(scope="myproj-billing", task_id="TSK-02")
        s_other = _make_signal(scope="otherproj", task_id="TSK-03")
        s_prefix_fp = _make_signal(scope="myproj2", task_id="TSK-04")
        result = MS._filter_signals_by_project(
            [s_same, s_sub, s_other, s_prefix_fp], "myproj"
        )
        self.assertIn(s_same, result)
        self.assertIn(s_sub, result)
        self.assertNotIn(s_other, result)
        self.assertNotIn(s_prefix_fp, result)
        self.assertEqual(len(result), 2)

    def test_returns_new_list_not_same_object(self):
        """원본 리스트를 변경하지 않고 새 리스트를 반환."""
        signals = [_make_signal(scope="myproj")]
        result = MS._filter_signals_by_project(signals, "myproj")
        self.assertIsNot(result, signals)

    def test_shared_scope_excluded(self):
        """scope='shared'는 project_name이 'shared'가 아니면 제외."""
        sig = _make_signal(scope="shared")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertNotIn(sig, result)

    def test_agent_pool_scope_excluded(self):
        """scope='agent-pool:12345-678'는 project_name=myproj 기준에서 제외."""
        sig = _make_signal(scope="agent-pool:12345-678")
        result = MS._filter_signals_by_project([sig], "myproj")
        self.assertNotIn(sig, result)


if __name__ == "__main__":
    unittest.main()
