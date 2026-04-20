"""Unit tests for list_tmux_panes() and capture_pane() in scripts/monitor-server.py.

Uses unittest.mock.patch to stub shutil.which and subprocess.run so the test suite
is portable across CI environments with or without tmux installed.

Covers QA checklist items:
- tmux 미설치 → list_tmux_panes() returns None (NOT [])
- tmux 설치됐으나 서버 없음 → []
- 존재하지 않는 pane id → tmux stderr string returned (no exception)
- pane_id 형식 검증 → ValueError (^%\\d+$ 미준수)
- ANSI escape 제거
- subprocess.run kwargs — shell=False, timeout=2 (list), timeout=3 (capture)
- PaneInfo dataclass field names per TRD §5.3
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from dataclasses import fields
from pathlib import Path
from unittest import mock


def _load_monitor_server():
    here = Path(__file__).resolve().parent
    src = here / "monitor-server.py"
    spec = importlib.util.spec_from_file_location("monitor_server_under_test", src)
    module = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_under_test"] = module
    spec.loader.exec_module(module)
    return module


MS = _load_monitor_server()


class ListTmuxPanesTests(unittest.TestCase):
    def test_returns_none_when_tmux_missing(self):
        with mock.patch.object(MS.shutil, "which", return_value=None):
            self.assertIsNone(MS.list_tmux_panes())

    def test_returns_empty_when_no_server_running(self):
        completed = subprocess.CompletedProcess(
            args=["tmux", "list-panes"],
            returncode=1,
            stdout="",
            stderr="no server running on /tmp/tmux-1000/default",
        )
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(MS.subprocess, "run", return_value=completed):
            result = MS.list_tmux_panes()
            self.assertEqual(result, [])

    def test_parses_normal_output(self):
        line = "\t".join([
            "dev", "@1", "%3", "0", "/home/u/proj", "bash", "12345", "1",
        ])
        completed = subprocess.CompletedProcess(
            args=["tmux", "list-panes"], returncode=0, stdout=line + "\n", stderr="",
        )
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(MS.subprocess, "run", return_value=completed):
            result = MS.list_tmux_panes()
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 1)
            p = result[0]
            self.assertEqual(p.window_name, "dev")
            self.assertEqual(p.window_id, "@1")
            self.assertEqual(p.pane_id, "%3")
            self.assertEqual(p.pane_index, 0)
            self.assertEqual(p.pane_current_path, "/home/u/proj")
            self.assertEqual(p.pane_current_command, "bash")
            self.assertEqual(p.pane_pid, 12345)
            self.assertTrue(p.is_active)

    def test_parses_inactive_pane(self):
        line = "\t".join(["w", "@1", "%4", "1", "/p", "zsh", "9999", "0"])
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout=line, stderr="",
        )
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(MS.subprocess, "run", return_value=completed):
            p = MS.list_tmux_panes()[0]
            self.assertFalse(p.is_active)
            self.assertEqual(p.pane_index, 1)
            self.assertEqual(p.pane_pid, 9999)

    def test_malformed_line_is_skipped(self):
        """If tab-split length != 8, the line is silently skipped."""
        good = "\t".join(["w", "@1", "%1", "0", "/p", "bash", "100", "1"])
        bad = "too\tshort\tline"
        stdout = f"{bad}\n{good}\n"
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout=stdout, stderr="",
        )
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(MS.subprocess, "run", return_value=completed):
            result = MS.list_tmux_panes()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].pane_id, "%1")

    def test_subprocess_run_kwargs_timeout_and_shell_false(self):
        """list_tmux_panes must use timeout=2, shell must be False (list-form)."""
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout="", stderr="",
        )
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(MS.subprocess, "run", return_value=completed) as r:
            MS.list_tmux_panes()
            self.assertTrue(r.called)
            _, kwargs = r.call_args
            args_list = r.call_args[0][0]
            self.assertIsInstance(args_list, list)
            self.assertEqual(args_list[0], "tmux")
            self.assertEqual(args_list[1], "list-panes")
            self.assertIn("-a", args_list)
            self.assertEqual(kwargs.get("timeout"), 2)
            self.assertFalse(kwargs.get("shell", False))

    def test_subprocess_timeout_expired_returns_empty_list(self):
        """A TimeoutExpired must not propagate; return [] instead."""
        with mock.patch.object(MS.shutil, "which", return_value="/usr/bin/tmux"), \
                mock.patch.object(
                    MS.subprocess, "run",
                    side_effect=subprocess.TimeoutExpired(cmd=["tmux"], timeout=2),
                ):
            self.assertEqual(MS.list_tmux_panes(), [])


class CapturePaneTests(unittest.TestCase):
    def test_raises_value_error_for_invalid_pane_id(self):
        with self.assertRaises(ValueError):
            MS.capture_pane("notapane")

    def test_raises_value_error_for_empty(self):
        with self.assertRaises(ValueError):
            MS.capture_pane("")

    def test_raises_value_error_for_missing_percent(self):
        with self.assertRaises(ValueError):
            MS.capture_pane("1")

    def test_raises_value_error_for_letters_after_percent(self):
        with self.assertRaises(ValueError):
            MS.capture_pane("%abc")

    def test_returns_stderr_string_for_nonexistent_pane(self):
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=1, stdout="",
            stderr="can't find pane %9999",
        )
        with mock.patch.object(MS.subprocess, "run", return_value=completed):
            out = MS.capture_pane("%9999")
            self.assertIn("%9999", out)
            self.assertIn("can't find pane", out)

    def test_strips_ansi_escape_sequences(self):
        raw = "A\x1b[31mB\x1b[0mC"
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout=raw, stderr="",
        )
        with mock.patch.object(MS.subprocess, "run", return_value=completed):
            out = MS.capture_pane("%1")
            self.assertEqual(out, "ABC")

    def test_strips_complex_ansi(self):
        raw = "\x1b[1;32mbold-green\x1b[0m normal \x1b[4munderline\x1b[24m"
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout=raw, stderr="",
        )
        with mock.patch.object(MS.subprocess, "run", return_value=completed):
            out = MS.capture_pane("%1")
            self.assertEqual(out, "bold-green normal underline")

    def test_subprocess_run_kwargs_timeout_and_shell_false(self):
        completed = subprocess.CompletedProcess(
            args=["tmux"], returncode=0, stdout="", stderr="",
        )
        with mock.patch.object(MS.subprocess, "run", return_value=completed) as r:
            MS.capture_pane("%5")
            args_list = r.call_args[0][0]
            _, kwargs = r.call_args
            self.assertIsInstance(args_list, list)
            self.assertEqual(args_list[0], "tmux")
            self.assertEqual(args_list[1], "capture-pane")
            self.assertIn("-t", args_list)
            self.assertIn("%5", args_list)
            self.assertIn("-p", args_list)
            self.assertIn("-S", args_list)
            self.assertIn("-500", args_list)
            self.assertEqual(kwargs.get("timeout"), 3)
            self.assertFalse(kwargs.get("shell", False))

    def test_timeout_expired_returns_stderr_like_message(self):
        """A TimeoutExpired must not propagate; a string is returned."""
        with mock.patch.object(
                MS.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(cmd=["tmux"], timeout=3)):
            out = MS.capture_pane("%7")
            self.assertIsInstance(out, str)
            self.assertTrue(len(out) > 0)


class PaneInfoShapeTests(unittest.TestCase):
    def test_fields_match_trd(self):
        expected = {
            "window_name", "window_id", "pane_id", "pane_index",
            "pane_current_path", "pane_current_command", "pane_pid", "is_active",
        }
        actual = {f.name for f in fields(MS.PaneInfo)}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
