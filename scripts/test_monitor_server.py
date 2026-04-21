"""
TDD 단위 테스트: monitor-server.py (TSK-02-02)
design.md QA 체크리스트 — 서버 측 SIGTERM 처리 섹션 기반
"""
import importlib
import importlib.util
import os
import pathlib
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _import_server():
    """monitor-server 모듈을 동적으로 import (매번 새로 로드)."""
    if "monitor_server" in sys.modules:
        del sys.modules["monitor_server"]
    spec = importlib.util.spec_from_file_location(
        "monitor_server", _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMonitorServerExists(unittest.TestCase):
    """monitor-server.py 파일이 존재해야 함"""

    def test_file_exists(self):
        server_path = _SCRIPT_DIR / "monitor-server.py"
        self.assertTrue(
            server_path.exists(),
            "scripts/monitor-server.py 파일이 존재해야 합니다.",
        )


class TestServerSourceStructure(unittest.TestCase):
    """monitor-server.py 소스 구조 검증 (구현 전 Red)"""

    def _source(self):
        server_path = _SCRIPT_DIR / "monitor-server.py"
        if not server_path.exists():
            self.skipTest("monitor-server.py 미존재")
        return server_path.read_text(encoding="utf-8")

    def test_serve_forever_present(self):
        self.assertIn("serve_forever", self._source())

    def test_finally_block_present(self):
        self.assertIn("finally", self._source())

    def test_getpid_present(self):
        """서버는 자신의 PID를 파일에 기록해야 함"""
        self.assertIn("getpid", self._source())

    def test_platform_branch_present(self):
        """플랫폼 분기(win32) 코드가 있어야 함"""
        src = self._source()
        self.assertTrue(
            'sys.platform != "win32"' in src or 'sys.platform == "win32"' in src,
            "플랫폼 분기 코드가 있어야 합니다.",
        )

    def test_sigterm_handler_registration(self):
        """SIGTERM 핸들러 등록 코드가 있어야 함"""
        src = self._source()
        self.assertIn("SIGTERM", src)

    def test_pid_file_pattern(self):
        """PID 파일 패턴 dev-monitor-{port}.pid 가 소스에 있어야 함"""
        src = self._source()
        self.assertIn("dev-monitor-", src)
        self.assertIn(".pid", src)

    def test_no_python3_hardcoding(self):
        """python3 하드코딩 금지"""
        import re
        src = self._source()
        hardcoded = re.findall(r'["\']python3["\']', src)
        self.assertEqual(len(hardcoded), 0, f"python3 하드코딩 발견: {hardcoded}")

    def test_127_binding(self):
        """127.0.0.1 로컬 바인딩이어야 함"""
        self.assertIn("127.0.0.1", self._source())

    def test_threading_http_server(self):
        """ThreadingHTTPServer 사용"""
        self.assertIn("ThreadingHTTPServer", self._source())


class TestServerPidFilePath(unittest.TestCase):
    """pid_file_path() 함수 검증"""

    def test_filename_pattern(self):
        ms = _import_server()
        if not hasattr(ms, "pid_file_path"):
            self.skipTest("pid_file_path 함수 미존재")
        result = ms.pid_file_path(7321)
        self.assertEqual(result.name, "dev-monitor-7321.pid")

    def test_is_in_temp_dir(self):
        ms = _import_server()
        if not hasattr(ms, "pid_file_path"):
            self.skipTest("pid_file_path 함수 미존재")
        result = ms.pid_file_path(7321)
        self.assertEqual(result.parent, pathlib.Path(tempfile.gettempdir()))

    def test_custom_port(self):
        ms = _import_server()
        if not hasattr(ms, "pid_file_path"):
            self.skipTest("pid_file_path 함수 미존재")
        result = ms.pid_file_path(8080)
        self.assertIn("8080", result.name)


class TestCleanupPidFile(unittest.TestCase):
    """cleanup_pid_file() — finally 블록 위임 함수"""

    def test_removes_existing_pid_file(self):
        ms = _import_server()
        if not hasattr(ms, "cleanup_pid_file"):
            self.skipTest("cleanup_pid_file 함수 미존재")
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-cleanup-{os.getpid()}.pid"
        with open(str(tmp_pid), "w", encoding="utf-8", newline="\n") as f:
            f.write(str(os.getpid()))
        try:
            ms.cleanup_pid_file(tmp_pid)
            self.assertFalse(tmp_pid.exists(), "PID 파일이 삭제되어야 합니다.")
        finally:
            if tmp_pid.exists():
                tmp_pid.unlink(missing_ok=True)

    def test_nonexistent_file_is_safe(self):
        """없는 PID 파일 정리는 예외 없이 통과 (missing_ok=True)"""
        ms = _import_server()
        if not hasattr(ms, "cleanup_pid_file"):
            self.skipTest("cleanup_pid_file 함수 미존재")
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no-such-server-pid-xyz.pid"
        try:
            ms.cleanup_pid_file(nonexistent)
        except Exception as e:
            self.fail(f"cleanup_pid_file raised {e} for nonexistent file")


class TestSetupSignalHandler(unittest.TestCase):
    """_setup_signal_handler() 검증"""

    def test_function_exists(self):
        ms = _import_server()
        has_func = hasattr(ms, "_setup_signal_handler") or hasattr(ms, "setup_signal_handler")
        self.assertTrue(has_func, "SIGTERM 핸들러 등록 함수가 있어야 합니다.")

    @unittest.skipIf(sys.platform == "win32", "Windows에서는 SIGTERM 핸들러 미등록")
    def test_registers_sigterm_handler_on_unix(self):
        """Unix에서 호출 후 SIGTERM 핸들러가 SIG_DFL이 아니어야 함"""
        ms = _import_server()
        mock_server = mock.MagicMock()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-sig-reg-{os.getpid()}.pid"
        with open(str(tmp_pid), "w", encoding="utf-8", newline="\n") as f:
            f.write(str(os.getpid()))

        original_handler = signal.getsignal(signal.SIGTERM)
        try:
            fn = getattr(ms, "_setup_signal_handler", None) or getattr(
                ms, "setup_signal_handler", None
            )
            fn(mock_server, tmp_pid)
            new_handler = signal.getsignal(signal.SIGTERM)
            self.assertNotEqual(
                new_handler,
                signal.SIG_DFL,
                "SIGTERM 핸들러가 등록되어야 합니다.",
            )
        finally:
            signal.signal(
                signal.SIGTERM,
                original_handler if original_handler is not None else signal.SIG_DFL,
            )
            if tmp_pid.exists():
                tmp_pid.unlink()

    @unittest.skipIf(sys.platform == "win32", "Windows 전용 테스트 아님")
    def test_sigterm_calls_server_shutdown(self):
        """SIGTERM 수신 시 server.shutdown()이 (비동기적으로) 호출되어야 함"""
        ms = _import_server()
        mock_server = mock.MagicMock()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-sigterm-sh-{os.getpid()}.pid"
        with open(str(tmp_pid), "w", encoding="utf-8", newline="\n") as f:
            f.write(str(os.getpid()))

        original_handler = signal.getsignal(signal.SIGTERM)
        try:
            fn = getattr(ms, "_setup_signal_handler", None) or getattr(
                ms, "setup_signal_handler", None
            )
            fn(mock_server, tmp_pid)

            # 현재 프로세스에 SIGTERM 전송 → 핸들러 트리거
            os.kill(os.getpid(), signal.SIGTERM)

            # shutdown은 별도 스레드에서 호출되므로 짧은 대기
            time.sleep(0.3)
            mock_server.shutdown.assert_called()
        finally:
            signal.signal(
                signal.SIGTERM,
                original_handler if original_handler is not None else signal.SIG_DFL,
            )
            if tmp_pid.exists():
                tmp_pid.unlink()


class TestServerParseArgs(unittest.TestCase):
    """서버 argparse 검증"""

    def test_default_port(self):
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertEqual(args.port, 7321)

    def test_custom_port(self):
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args(["--port", "8080"])
        self.assertEqual(args.port, 8080)

    def test_default_docs(self):
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertEqual(args.docs, "docs")

    def test_custom_docs(self):
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args(["--docs", "my-docs"])
        self.assertEqual(args.docs, "my-docs")


if __name__ == "__main__":
    unittest.main()
