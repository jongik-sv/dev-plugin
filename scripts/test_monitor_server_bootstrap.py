"""Unit tests for TSK-01-01: HTTP 서버 뼈대 및 argparse 진입점.

QA 체크리스트 기반 테스트:
- build_arg_parser() / main(argv) 기반 argparse 검증
- ThreadingHTTPServer 127.0.0.1 바인딩 확인
- GET / → 200 or 501 (stub 허용)
- POST / → 405
- GET /api/state → application/json
- GET /pane/%1 → 400 or HTML (서버 크래시 없음)
- GET /nonexistent → 404
- --no-tmux 인자 파싱 에러 없음
- log_message: stderr 출력, stdout 비움

실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

from __future__ import annotations

import importlib.util
import io
import socket
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from unittest.mock import patch


# monitor-server.py는 파일명에 하이픈이 있어 일반 import 불가 → importlib로 로드
_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)


def _find_free_port() -> int:
    """OS가 할당 가능한 ephemeral port를 반환한다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ServerContext:
    """main(argv)를 백그라운드 스레드로 기동하고 종료하는 컨텍스트 매니저."""

    def __init__(self, port: int, extra_args: Optional[list] = None):
        self.port = port
        self.extra_args = extra_args or []
        self._thread: Optional[threading.Thread] = None
        self._server = None

    def start(self) -> None:
        """서버를 백그라운드 스레드에서 기동한다."""
        ready = threading.Event()
        server_holder = []

        original_main = monitor_server.main

        def patched_main(argv=None):
            # main() 내부에서 서버 생성 후 serve_forever 전에 가로채기 위해
            # ThreadingMonitorServer.__init__을 패치
            original_cls_init = monitor_server.ThreadingMonitorServer.__init__

            def _captured_init(srv_self, *args, **kwargs):
                original_cls_init(srv_self, *args, **kwargs)
                server_holder.append(srv_self)
                ready.set()

            with patch.object(monitor_server.ThreadingMonitorServer, "__init__", _captured_init):
                original_main(argv)

        self._thread = threading.Thread(
            target=patched_main,
            args=(["--port", str(self.port)] + self.extra_args,),
            daemon=True,
        )
        self._thread.start()
        ready.wait(timeout=5)
        if server_holder:
            self._server = server_holder[0]

        # 서버 소켓이 실제로 LISTEN 상태가 될 때까지 대기 (최대 3초)
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()

    def __enter__(self) -> "_ServerContext":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


class TestArgParser(unittest.TestCase):
    """build_arg_parser() / argparse 기본 동작 검증."""

    def setUp(self):
        self.parser = monitor_server.build_arg_parser()

    def test_default_port(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.port, 7321)

    def test_default_docs(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.docs, "docs")

    def test_default_project_root(self):
        import os
        args = self.parser.parse_args([])
        self.assertEqual(args.project_root, os.getcwd())

    def test_default_max_pane_lines(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.max_pane_lines, 500)

    def test_default_refresh_seconds(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.refresh_seconds, 3)

    def test_default_no_tmux_false(self):
        args = self.parser.parse_args([])
        self.assertFalse(args.no_tmux)

    def test_no_tmux_flag(self):
        """--no-tmux 전달 시 파싱 에러 없음, no_tmux=True."""
        args = self.parser.parse_args(["--no-tmux"])
        self.assertTrue(args.no_tmux)

    def test_port_override(self):
        args = self.parser.parse_args(["--port", "8080"])
        self.assertEqual(args.port, 8080)

    def test_docs_override(self):
        args = self.parser.parse_args(["--docs", "my-docs"])
        self.assertEqual(args.docs, "my-docs")

    def test_project_root_override(self):
        args = self.parser.parse_args(["--project-root", "/tmp/proj"])
        self.assertEqual(args.project_root, "/tmp/proj")

    def test_max_pane_lines_override(self):
        args = self.parser.parse_args(["--max-pane-lines", "200"])
        self.assertEqual(args.max_pane_lines, 200)

    def test_refresh_seconds_override(self):
        args = self.parser.parse_args(["--refresh-seconds", "10"])
        self.assertEqual(args.refresh_seconds, 10)

    def test_help_contains_all_args(self):
        """--help 출력에 모든 CLI 인자가 포함된다."""
        buf = io.StringIO()
        try:
            self.parser.print_help(file=buf)
        except SystemExit:
            pass
        help_text = buf.getvalue()
        for arg in ("--port", "--docs", "--project-root", "--max-pane-lines",
                    "--refresh-seconds", "--no-tmux"):
            self.assertIn(arg, help_text, f"{arg} not in --help output")


class TestServerBinding(unittest.TestCase):
    """서버 바인딩 및 기본 HTTP 동작 검증."""

    def test_root_returns_200_or_501(self):
        """GET / → 200 또는 501(stub 허용)."""
        port = _find_free_port()
        with _ServerContext(port):
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=5
            )
            self.assertIn(resp.status, (200, 501))

    def test_post_returns_405(self):
        """POST / → 405 Method Not Allowed."""
        port = _find_free_port()
        with _ServerContext(port):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                data=b"",
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
                self.fail("Expected HTTPError 405")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 405)

    def test_localhost_only_binding(self):
        """서버가 127.0.0.1에만 바인딩되어 있음을 소켓 레벨에서 확인."""
        port = _find_free_port()
        with _ServerContext(port) as ctx:
            server = ctx._server
            self.assertIsNotNone(server, "server 인스턴스를 가져오지 못했습니다")
            host = server.server_address[0]
            self.assertEqual(host, "127.0.0.1",
                             f"0.0.0.0 바인딩 금지 위반: {host!r}")

    def test_api_state_returns_json(self):
        """GET /api/state → Content-Type: application/json."""
        port = _find_free_port()
        with _ServerContext(port):
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/state", timeout=5
            )
            ct = resp.getheader("Content-Type", "")
            self.assertIn("application/json", ct)

    def test_pane_invalid_id_no_crash(self):
        """GET /pane/%1 → 400 또는 HTML 에러 — 서버 크래시 없음."""
        port = _find_free_port()
        with _ServerContext(port):
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/pane/%251", timeout=5
                )
                # 200 응답이어도 크래시 없으면 통과
                self.assertIsNotNone(resp)
            except urllib.error.HTTPError as exc:
                # 400이면 OK
                self.assertEqual(exc.code, 400)

    def test_nonexistent_path_returns_404(self):
        """GET /nonexistent → 404."""
        port = _find_free_port()
        with _ServerContext(port):
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/nonexistent", timeout=5
                )
                self.fail("Expected HTTPError 404")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 404)

    def test_no_tmux_flag_no_parse_error(self):
        """--no-tmux 전달 시 인자 파싱 에러 없이 서버가 기동된다."""
        port = _find_free_port()
        with _ServerContext(port, extra_args=["--no-tmux"]):
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/state", timeout=5
            )
            self.assertIn(resp.status, (200, 501))


class TestLogMessage(unittest.TestCase):
    """log_message: stderr에 요청 라인 출력, stdout 비움."""

    def test_log_message_stderr_not_stdout(self):
        """log_message()가 stderr에 쓰고 stdout에는 쓰지 않는다.

        MonitorHandler 인스턴스를 직접 생성하여 log_message를 호출하는
        단위 테스트 (실제 서버 기동 불필요).
        """
        # MonitorHandler를 직접 인스턴스화하기 어려우므로 클래스 메서드를 직접 호출
        # 대신 MagicMock으로 최소한의 handler를 만든다
        from unittest.mock import MagicMock
        handler = MagicMock()
        handler.requestline = "GET /api/state HTTP/1.1"
        # log_message를 언바운드 메서드로 호출
        captured_stderr = io.StringIO()
        captured_stdout = io.StringIO()
        with patch("sys.stderr", captured_stderr), patch("sys.stdout", captured_stdout):
            monitor_server.MonitorHandler.log_message(handler, "%s", "GET /api/state HTTP/1.1")

        stderr_out = captured_stderr.getvalue()
        stdout_out = captured_stdout.getvalue()
        self.assertEqual(stdout_out, "", f"stdout에 출력이 있으면 안 됨: {stdout_out!r}")
        # stderr에는 요청 라인 일부가 포함되어야 한다
        self.assertIn("GET", stderr_out)


class TestMainFunctionality(unittest.TestCase):
    """main() 함수 직접 호출 테스트."""

    def test_main_binds_and_responds(self):
        """main(['--port', port]) 호출 시 서버가 기동되고 응답한다."""
        port = _find_free_port()
        with _ServerContext(port):
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/state", timeout=5
            )
            self.assertEqual(resp.status, 200)

    def test_server_attributes_injected(self):
        """server.project_root, docs_dir 등 속성이 서버 인스턴스에 주입된다."""
        port = _find_free_port()
        with _ServerContext(port, extra_args=["--docs", "my-docs",
                                              "--project-root", "/tmp/test"]) as ctx:
            server = ctx._server
            self.assertIsNotNone(server)
            self.assertEqual(server.docs_dir, "my-docs")
            self.assertEqual(server.project_root, "/tmp/test")

    def test_put_returns_405(self):
        """PUT / → 405."""
        port = _find_free_port()
        with _ServerContext(port):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                data=b"",
                method="PUT",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
                self.fail("Expected HTTPError 405")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 405)

    def test_delete_returns_405(self):
        """DELETE / → 405."""
        port = _find_free_port()
        with _ServerContext(port):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                data=b"",
                method="DELETE",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
                self.fail("Expected HTTPError 405")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 405)


if __name__ == "__main__":
    unittest.main()
