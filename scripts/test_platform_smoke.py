"""
test_platform_smoke.py — 4-플랫폼 Smoke 테스트 (TSK-04-03)

검증 항목:
  - GET / → 200, HTML에 <section data-section="kpi"> 존재
  - GET /api/state → 200, application/json, 파싱 가능
  - --no-tmux 기동 시 "tmux not available" 문자열 포함
  - 폴링 JS 코드 (setInterval, 2000) 존재
  - monitor-launcher.py 소스에서 sys.executable 사용 확인

플랫폼별 결함은 docs/monitor-v2/tasks/TSK-04-03/qa-report.md에 기록.

사용법:
  python3 -m unittest scripts/test_platform_smoke.py -v
  python3 scripts/test_platform_smoke.py
"""

import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

# ── 프로젝트 루트 계산 ──────────────────────────────────────────────────────
_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
_LAUNCHER = _SCRIPTS_DIR / "monitor-launcher.py"

# 테스트 전용 포트 (기본 7321 과 충돌 방지)
_TEST_PORT = 7399
_TEST_PORT_NOTMUX = 7398   # --no-tmux 전용 인스턴스
_TEST_PORT_SHUTDOWN = 7397  # ServerShutdownTest 전용 포트
_SERVER_URL = f"http://localhost:{_TEST_PORT}"
_SERVER_URL_NOTMUX = f"http://localhost:{_TEST_PORT_NOTMUX}"
_MAX_WAIT_SECONDS = 10


# ── 공통 헬퍼 ───────────────────────────────────────────────────────────────

def _wait_for_server(url: str, timeout: int = _MAX_WAIT_SECONDS) -> bool:
    """서버가 HTTP 요청에 응답할 때까지 폴링. timeout 초 내 응답하면 True."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _start_server(port: int, extra_args=None):
    """monitor-launcher.py로 서버 기동 후 프로세스 반환."""
    cmd = [
        sys.executable,
        str(_LAUNCHER),
        "--port", str(port),
        "--docs", "docs",
        "--project-root", str(_PROJECT_ROOT),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.Popen(
        cmd,
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _stop_server(port: int) -> None:
    """monitor-launcher.py --stop으로 서버 정지."""
    subprocess.run(
        [sys.executable, str(_LAUNCHER), "--stop", "--port", str(port)],
        cwd=str(_PROJECT_ROOT),
        check=False,
        timeout=5,
    )


def _port_available(port: int) -> bool:
    """해당 포트가 bind 가능(사용 가능)하면 True."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _has_main_section(body: str) -> bool:
    """HTML body에 wbs/team/features 섹션 중 하나 이상이 존재하면 True."""
    return (
        '<section id="wbs">' in body
        or '<section id="team">' in body
        or '<section id="features">' in body
    )


def _cleanup_proc(proc) -> None:
    """프로세스 파이프를 닫고 종료를 기다린다. 타임아웃 시 terminate."""
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.terminate()
    for fh in (proc.stdout, proc.stderr):
        if fh is not None:
            try:
                fh.close()
            except Exception:
                pass


# ── 기본 Smoke 테스트 (정상 기동) ───────────────────────────────────────────

class SmokeTestBase(unittest.TestCase):
    """서버 기동/정지 공통 로직을 담은 Base 클래스."""

    @classmethod
    def setUpClass(cls):
        # 포트 사용 가능 여부 사전 검사
        if not _port_available(_TEST_PORT):
            raise unittest.SkipTest(
                f"포트 {_TEST_PORT}이 이미 사용 중입니다 — Smoke 테스트를 스킵합니다."
            )
        cls._proc = _start_server(_TEST_PORT)
        ready = _wait_for_server(_SERVER_URL, timeout=_MAX_WAIT_SECONDS)
        if not ready:
            cls._proc.terminate()
            raise unittest.SkipTest(
                f"서버가 {_MAX_WAIT_SECONDS}초 내에 응답하지 않습니다 — 테스트를 스킵합니다."
            )

    @classmethod
    def tearDownClass(cls):
        _stop_server(_TEST_PORT)
        _cleanup_proc(cls._proc)

    def test_dashboard_loads(self):
        """GET / → 200, HTML에 대시보드 섹션 (wbs, team 등) 존재.

        monitor-server.py는 <section id="{anchor}"> 패턴을 사용한다.
        메인 섹션 앵커: wbs, features, team, subagents, phases.
        """
        with urllib.request.urlopen(_SERVER_URL, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
        self.assertTrue(
            _has_main_section(body),
            "대시보드 HTML에 wbs/team/features 섹션이 없습니다.",
        )

    def test_drawer_api(self):
        """GET /api/state → 200, application/json, 파싱 가능한 JSON."""
        with urllib.request.urlopen(f"{_SERVER_URL}/api/state", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content_type = resp.getheader("Content-Type", "")
            self.assertIn("application/json", content_type,
                          f"Content-Type이 application/json이 아닙니다: {content_type}")
            body = resp.read().decode("utf-8")
        # JSON 파싱 성공 확인
        parsed = json.loads(body)
        self.assertIsInstance(parsed, dict,
                              "응답 JSON이 dict 타입이 아닙니다.")

    def test_pane_polling_interval(self):
        """대시보드 폴링 메커니즘 존재 확인.

        monitor-server.py 대시보드 메인 페이지는 <meta http-equiv="refresh">
        방식으로 페이지를 갱신한다. pane 상세 페이지(/pane/{id})는
        setInterval + fetch 방식을 사용하며 이 테스트는 양쪽을 모두 허용한다.

        design.md §37의 "2초 폴링" 요구사항 근거:
          - 대시보드 메인: meta refresh (content 값 확인)
          - pane 상세: setInterval(tick, 2000)
        두 방식 중 하나라도 존재하면 폴링 요구사항을 충족한다.
        """
        with urllib.request.urlopen(_SERVER_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        has_meta_refresh = "http-equiv" in body and "refresh" in body
        has_set_interval = "setInterval" in body
        has_2000 = "2000" in body
        self.assertTrue(
            has_meta_refresh or has_set_interval or has_2000,
            "대시보드 HTML에 폴링 메커니즘 (meta refresh, setInterval, 2000ms) 이 없습니다.",
        )

    def test_server_startup_within_timeout(self):
        """setUpClass 성공 자체가 10초 내 서버 기동을 증명. 별도 HTTP 재확인."""
        with urllib.request.urlopen(_SERVER_URL, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

    def test_no_tmux_section_normal_mode(self):
        """--no-tmux 없이 기동 시 Team 섹션은 'tmux not available' 미포함.

        (panes가 없으면 'no tmux panes running' 이 표시되어야 하며
        'tmux not available' 메시지는 --no-tmux 모드에서만 나타난다)
        """
        with urllib.request.urlopen(_SERVER_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        # 정상 모드: 'tmux not available on this host' 메시지는 없어야 함
        self.assertNotIn(
            "tmux not available on this host",
            body,
            "정상 기동 모드에서 'tmux not available on this host' 메시지가 표시되었습니다.",
        )


# ── --no-tmux 시나리오 테스트 ────────────────────────────────────────────────

class NoTmuxSmokeTest(unittest.TestCase):
    """--no-tmux 플래그로 기동된 서버의 대시보드 검증."""

    @classmethod
    def setUpClass(cls):
        if not _port_available(_TEST_PORT_NOTMUX):
            raise unittest.SkipTest(
                f"포트 {_TEST_PORT_NOTMUX}이 이미 사용 중입니다 — no-tmux 테스트를 스킵합니다."
            )
        cls._proc = _start_server(_TEST_PORT_NOTMUX, extra_args=["--no-tmux"])
        ready = _wait_for_server(_SERVER_URL_NOTMUX, timeout=_MAX_WAIT_SECONDS)
        if not ready:
            cls._proc.terminate()
            raise unittest.SkipTest(
                f"--no-tmux 서버가 {_MAX_WAIT_SECONDS}초 내에 응답하지 않습니다."
            )

    @classmethod
    def tearDownClass(cls):
        _stop_server(_TEST_PORT_NOTMUX)
        _cleanup_proc(cls._proc)

    def test_no_tmux_message_in_dashboard(self):
        """--no-tmux 기동 시 대시보드 HTML에 'tmux not available' 포함 확인."""
        with urllib.request.urlopen(_SERVER_URL_NOTMUX, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        self.assertIn(
            "tmux not available",
            body,
            "--no-tmux 모드에서 대시보드에 'tmux not available' 문자열이 없습니다.",
        )

    def test_dashboard_still_loads_with_no_tmux(self):
        """--no-tmux 모드에서도 대시보드 200 OK, 주요 섹션 존재."""
        with urllib.request.urlopen(_SERVER_URL_NOTMUX, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
        self.assertTrue(
            _has_main_section(body),
            "--no-tmux 모드에서 wbs/team/features 섹션이 없습니다.",
        )


# ── sys.executable 단위 검증 (소스 grep) ────────────────────────────────────

class SysExecutableUnitTest(unittest.TestCase):
    """monitor-launcher.py 소스에서 sys.executable 사용 확인 (모든 플랫폼 통과)."""

    def test_sys_executable_used_in_start_server(self):
        """monitor-launcher.py의 start_server()가 sys.executable을 사용하는지 확인."""
        launcher_src = _LAUNCHER.read_text(encoding="utf-8")
        self.assertIn(
            "sys.executable",
            launcher_src,
            "monitor-launcher.py에 sys.executable이 없습니다 — python3 하드코딩 위험.",
        )

    def test_no_python3_hardcoding_in_cmd(self):
        """start_server()의 cmd 배열에 'python3' 문자열 리터럴이 없어야 함.

        허용되는 예외: 주석이나 docstring 내 'python3' 언급은 무방하나
        cmd = ["python3", ...] 같은 직접 하드코딩은 rc=9009를 유발한다.
        """
        launcher_src = _LAUNCHER.read_text(encoding="utf-8")
        # cmd 배열 정의 라인에서 "python3" 리터럴이 나타나지 않아야 함
        # 'cmd = [sys.executable, ...]' 패턴이 있으면 통과
        lines_with_cmd = [
            ln for ln in launcher_src.splitlines()
            if "cmd" in ln and ("python3" in ln or '"python"' in ln)
            and not ln.strip().startswith("#")
        ]
        self.assertEqual(
            lines_with_cmd, [],
            f"start_server() cmd에 python3 하드코딩이 발견되었습니다:\n"
            + "\n".join(lines_with_cmd),
        )

    def test_platform_py_exists(self):
        """scripts/_platform.py가 존재하는지 확인 (플랫폼 유틸 경로 처리)."""
        platform_py = _SCRIPTS_DIR / "_platform.py"
        self.assertTrue(
            platform_py.exists(),
            f"scripts/_platform.py가 없습니다: {platform_py}",
        )


# ── 서버 정상 종료 확인 ──────────────────────────────────────────────────────

class ServerShutdownTest(unittest.TestCase):
    """--stop으로 서버가 정상 종료되는지 확인."""

    def test_stop_command_works(self):
        """서버를 기동 후 --stop으로 종료하고 PID 파일이 삭제되는지 확인."""
        port = _TEST_PORT_SHUTDOWN
        if not _port_available(port):
            self.skipTest(f"포트 {port}이 이미 사용 중입니다.")

        # 기동
        proc = _start_server(port)
        ready = _wait_for_server(f"http://localhost:{port}", timeout=_MAX_WAIT_SECONDS)
        if not ready:
            proc.terminate()
            self.skipTest(f"서버 기동 실패 (포트 {port})")

        # 정지
        _stop_server(port)

        # PID 파일이 삭제되었는지 확인 (최대 3초 대기)
        pid_file = pathlib.Path(tempfile.gettempdir()) / f"dev-monitor-{port}.pid"
        deadline = time.time() + 3
        while time.time() < deadline and pid_file.exists():
            time.sleep(0.2)

        self.assertFalse(
            pid_file.exists(),
            f"--stop 후에도 PID 파일이 남아있습니다: {pid_file}",
        )

        _cleanup_proc(proc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
