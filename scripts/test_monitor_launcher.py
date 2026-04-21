"""
TDD 단위 테스트: monitor-launcher.py
design.md QA 체크리스트 기반
"""
import importlib
import importlib.util
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

# monitor-launcher 모듈을 동적으로 import
_SCRIPT_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))


def _import_launcher():
    """monitor-launcher 모듈을 import (매번 새로 로드)."""
    if "monitor_launcher" in sys.modules:
        del sys.modules["monitor_launcher"]
    spec = importlib.util.spec_from_file_location(
        "monitor_launcher", _SCRIPT_DIR / "monitor-launcher.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPidFilePath(unittest.TestCase):
    def test_returns_path_object(self):
        ml = _import_launcher()
        result = ml.pid_file_path(7321)
        self.assertIsInstance(result, pathlib.Path)

    def test_filename_contains_port(self):
        ml = _import_launcher()
        result = ml.pid_file_path(8080)
        self.assertIn("8080", result.name)

    def test_filename_pattern(self):
        ml = _import_launcher()
        result = ml.pid_file_path(7321)
        self.assertEqual(result.name, "dev-monitor-7321.pid")

    def test_is_in_temp_dir(self):
        ml = _import_launcher()
        result = ml.pid_file_path(7321)
        self.assertEqual(result.parent, pathlib.Path(tempfile.gettempdir()))


class TestLogFilePath(unittest.TestCase):
    def test_filename_pattern(self):
        ml = _import_launcher()
        result = ml.log_file_path(7321)
        self.assertEqual(result.name, "dev-monitor-7321.log")

    def test_is_in_temp_dir(self):
        ml = _import_launcher()
        result = ml.log_file_path(7321)
        self.assertEqual(result.parent, pathlib.Path(tempfile.gettempdir()))


class TestIsAlive(unittest.TestCase):
    def test_current_process_is_alive(self):
        ml = _import_launcher()
        self.assertTrue(ml.is_alive(os.getpid()))

    def test_nonexistent_pid_returns_false(self):
        ml = _import_launcher()
        # PID 999999999는 일반적으로 존재하지 않음
        self.assertFalse(ml.is_alive(999999999))

    def test_negative_pid_returns_false(self):
        ml = _import_launcher()
        self.assertFalse(ml.is_alive(-1))


class TestReadPid(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            suffix=".pid", delete=False, mode="w"
        )
        self.tmp_path = pathlib.Path(self.tmp.name)

    def tearDown(self):
        if self.tmp_path.exists():
            self.tmp_path.unlink()

    def test_reads_valid_pid(self):
        ml = _import_launcher()
        self.tmp.write("12345\n")
        self.tmp.close()
        result = ml.read_pid(self.tmp_path)
        self.assertEqual(result, 12345)

    def test_returns_none_for_nonexistent_file(self):
        ml = _import_launcher()
        self.tmp.close()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no_such_file_xyz.pid"
        result = ml.read_pid(nonexistent)
        self.assertIsNone(result)

    def test_returns_none_for_invalid_content(self):
        ml = _import_launcher()
        self.tmp.write("not_a_number\n")
        self.tmp.close()
        result = ml.read_pid(self.tmp_path)
        self.assertIsNone(result)

    def test_returns_none_for_empty_file(self):
        ml = _import_launcher()
        self.tmp.close()
        result = ml.read_pid(self.tmp_path)
        self.assertIsNone(result)


class TestTestPort(unittest.TestCase):
    def test_available_port_returns_true(self):
        ml = _import_launcher()
        # 임시 서버를 바인딩해 사용 가능한 포트 찾기
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
        s.close()
        self.assertTrue(ml.test_port(free_port))

    def test_occupied_port_returns_false(self):
        ml = _import_launcher()
        # 포트를 미리 점유 (SO_REUSEADDR 미설정)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        occupied_port = s.getsockname()[1]
        try:
            result = ml.test_port(occupied_port)
            self.assertFalse(result)
        finally:
            s.close()


class TestStartServer(unittest.TestCase):
    """start_server: Popen detach + PID 파일 기록 테스트"""

    def _make_tmp_pid_path(self):
        return pathlib.Path(tempfile.gettempdir()) / f"test-monitor-pid-{os.getpid()}.pid"

    def tearDown(self):
        pid_path = self._make_tmp_pid_path()
        if pid_path.exists():
            pid_path.unlink()
        log_path = pathlib.Path(tempfile.gettempdir()) / "test-monitor.log"
        if log_path.exists():
            log_path.unlink()

    def test_pid_file_written_after_start(self):
        ml = _import_launcher()
        pid_path = self._make_tmp_pid_path()

        with mock.patch.object(ml, "pid_file_path", return_value=pid_path), \
             mock.patch.object(ml, "log_file_path",
                               return_value=pathlib.Path(tempfile.gettempdir()) / "test-monitor.log"), \
             mock.patch("subprocess.Popen") as mock_popen:
            mock_proc = mock.MagicMock()
            mock_proc.pid = 99999
            mock_popen.return_value = mock_proc
            ml.start_server(7321, "docs", str(pathlib.Path(__file__).parent.parent))

        self.assertTrue(pid_path.exists())
        content = pid_path.read_text().strip()
        self.assertEqual(content, "99999")

    def test_popen_called_with_sys_executable(self):
        ml = _import_launcher()
        pid_path = self._make_tmp_pid_path()

        with mock.patch.object(ml, "pid_file_path", return_value=pid_path), \
             mock.patch.object(ml, "log_file_path",
                               return_value=pathlib.Path(tempfile.gettempdir()) / "test-monitor.log"), \
             mock.patch("subprocess.Popen") as mock_popen:
            mock_proc = mock.MagicMock()
            mock_proc.pid = 99999
            mock_popen.return_value = mock_proc
            ml.start_server(7321, "docs", str(pathlib.Path(__file__).parent.parent))

        call_args = mock_popen.call_args
        cmd = call_args[0][0]  # 첫 번째 positional 인자
        self.assertEqual(cmd[0], sys.executable)

    def test_no_python3_hardcoding_in_source(self):
        """monitor-launcher.py 소스에 'python3' 하드코딩이 없어야 함"""
        launcher_path = _SCRIPT_DIR / "monitor-launcher.py"
        if not launcher_path.exists():
            self.skipTest("monitor-launcher.py 미존재 (구현 전)")
        source = launcher_path.read_text()
        self.assertIn("sys.executable", source)
        # 'python3' 리터럴 하드코딩 금지 (subprocess 인자로 직접 쓰는 경우)
        import re
        # subprocess 호출에서 python3 직접 사용 여부 체크 (문자열 리터럴로)
        hardcoded = re.findall(r'["\']python3["\']', source)
        self.assertEqual(len(hardcoded), 0,
                         f"python3 하드코딩 발견: {hardcoded}")


class TestPlatformBranch(unittest.TestCase):
    """플랫폼 분기 코드가 존재하는지 확인"""

    def test_win32_branch_exists(self):
        launcher_path = _SCRIPT_DIR / "monitor-launcher.py"
        if not launcher_path.exists():
            self.skipTest("monitor-launcher.py 미존재 (구현 전)")
        source = launcher_path.read_text()
        self.assertIn('sys.platform == "win32"', source)

    def test_detached_process_flag_exists(self):
        launcher_path = _SCRIPT_DIR / "monitor-launcher.py"
        if not launcher_path.exists():
            self.skipTest("monitor-launcher.py 미존재 (구현 전)")
        source = launcher_path.read_text()
        self.assertIn("DETACHED_PROCESS", source)

    def test_start_new_session_flag_exists(self):
        launcher_path = _SCRIPT_DIR / "monitor-launcher.py"
        if not launcher_path.exists():
            self.skipTest("monitor-launcher.py 미존재 (구현 전)")
        source = launcher_path.read_text()
        self.assertIn("start_new_session=True", source)


class TestSkillMdContent(unittest.TestCase):
    """SKILL.md YAML frontmatter 및 키워드 검증"""

    def _read_skill_md(self):
        path = pathlib.Path(__file__).parent.parent / "skills" / "dev-monitor" / "SKILL.md"
        if not path.exists():
            self.skipTest("SKILL.md 미존재")
        return path.read_text()

    def test_name_is_dev_monitor(self):
        content = self._read_skill_md()
        self.assertIn("name: dev-monitor", content)

    def test_description_contains_korean_monitoring(self):
        content = self._read_skill_md()
        self.assertIn("모니터링", content)

    def test_description_contains_korean_dashboard(self):
        content = self._read_skill_md()
        self.assertIn("대시보드", content)

    def test_description_contains_monitor_english(self):
        content = self._read_skill_md()
        self.assertIn("monitor", content)

    def test_description_contains_dashboard_english(self):
        content = self._read_skill_md()
        self.assertIn("dashboard", content)

    def test_default_port_7321(self):
        content = self._read_skill_md()
        self.assertIn("7321", content)

    def test_default_docs_mentioned(self):
        content = self._read_skill_md()
        self.assertIn("--docs", content)

    def test_stop_flag_mentioned(self):
        content = self._read_skill_md()
        self.assertIn("--stop", content)

    def test_status_flag_mentioned(self):
        content = self._read_skill_md()
        self.assertIn("--status", content)

    def test_not_placeholder(self):
        """placeholder 문구가 없어야 함 (완성본 확인)"""
        content = self._read_skill_md()
        self.assertNotIn("placeholder", content)


class TestStopServer(unittest.TestCase):
    """stop_server: SIGTERM + PID 파일 삭제 테스트"""

    def test_stop_removes_pid_file(self):
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-stop-{os.getpid()}.pid"
        tmp_pid.write_text(str(os.getpid()))

        with mock.patch("os.kill"), \
             mock.patch.object(ml, "pid_file_path", return_value=tmp_pid):
            ml.stop_server(7321)

        self.assertFalse(tmp_pid.exists())

    def test_stop_no_pid_file_is_noop(self):
        ml = _import_launcher()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no-such-pid-xyz.pid"

        with mock.patch.object(ml, "pid_file_path", return_value=nonexistent):
            try:
                ml.stop_server(7321)
            except Exception as e:
                self.fail(f"stop_server raised {e} unexpectedly")


class TestParseArgs(unittest.TestCase):
    """parse_args: 인자 파싱 테스트"""

    def test_default_port(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        self.assertEqual(args.port, 7321)

    def test_custom_port(self):
        ml = _import_launcher()
        args = ml.parse_args(["--port", "8080", "--project-root", "/tmp"])
        self.assertEqual(args.port, 8080)

    def test_default_docs(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        self.assertEqual(args.docs, "docs")

    def test_custom_docs(self):
        ml = _import_launcher()
        args = ml.parse_args(["--docs", "my-docs", "--project-root", "/tmp"])
        self.assertEqual(args.docs, "my-docs")

    def test_stop_flag_default_false(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        self.assertFalse(args.stop)

    def test_stop_flag(self):
        ml = _import_launcher()
        args = ml.parse_args(["--stop", "--project-root", "/tmp"])
        self.assertTrue(args.stop)

    def test_status_flag_default_false(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        self.assertFalse(args.status)

    def test_status_flag(self):
        ml = _import_launcher()
        args = ml.parse_args(["--status", "--project-root", "/tmp"])
        self.assertTrue(args.status)

    def test_project_root(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/my/project"])
        self.assertEqual(args.project_root, "/my/project")


if __name__ == "__main__":
    unittest.main()
