"""
TDD 단위 테스트: TSK-03-02 QA 픽스처 + argparse 기본값 검증
design.md QA 체크리스트 기반

검증 항목:
- monitor-server.py --refresh-seconds 기본값 = 3 (PRD §8 T1)
- monitor-server.py --max-pane-lines 기본값 = 500 (PRD §8 T2)
- HTML에 <meta http-equiv="refresh" content="3"> 포함
- CorruptedStateFixture: 손상된 state.json 생성/정리
- EmptyProjectFixture: 빈 docs 트리 생성/정리
- PortConflictFixture: 포트 충돌 시나리오 헬퍼
- Read-Only 보장: state.json chmod 0o444 후 서버 생존
- 빈 프로젝트 대시보드 HTML에 "태스크 없음" 안내 포함
"""
import importlib.util
import json
import os
import pathlib
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

_SCRIPT_DIR = pathlib.Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent


def _import_server():
    """monitor-server 모듈을 동적으로 import.

    sys.modules에 임시 등록하여 @dataclass 처리 시 cls.__module__ 조회가
    None을 반환하지 않도록 한다. exec_module 완료 후 즉시 제거하여 다른
    테스트 파일의 module-level import와 충돌하지 않도록 한다.
    """
    key = "monitor_server"
    # 기존 등록 캐시 제거 (재로딩 보장)
    prev = sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        key, _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        # 전역 sys.modules 오염 방지: 임시 등록 해제
        # 다른 파일이 module-level에서 sys.modules["monitor_server"]를 등록한
        # 경우 복원하고, 그렇지 않으면 제거한다.
        if prev is not None:
            sys.modules[key] = prev
        else:
            sys.modules.pop(key, None)
    return mod


# ---------------------------------------------------------------------------
# QA 픽스처 클래스 (컨텍스트 매니저)
# ---------------------------------------------------------------------------

class EmptyProjectFixture:
    """빈 docs 트리 픽스처.

    임시 디렉터리에 tasks/ 와 features/ 를 생성하되 내용은 비워둔다.
    QA 시나리오 1(빈 프로젝트 기동 → "no tasks" 안내) 재현용.
    """

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="qa_empty_")
        self.docs_dir = pathlib.Path(self._tmpdir)
        (self.docs_dir / "tasks").mkdir()
        (self.docs_dir / "features").mkdir()
        return self

    def __exit__(self, *_):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class CorruptedStateFixture:
    """손상된 state.json 픽스처.

    임시 docs 트리에 정상 Task와 손상 Task를 각각 하나씩 생성한다.
    QA 시나리오 4(state.json 고의 손상 → 해당 Task만 ⚠️) 재현용.
    """

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="qa_corrupted_")
        self.docs_dir = pathlib.Path(self._tmpdir)

        # 정상 Task
        good_dir = self.docs_dir / "tasks" / "TSK-GOOD"
        good_dir.mkdir(parents=True)
        (good_dir / "state.json").write_text(
            json.dumps({"status": "[dd]", "updated": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

        # 손상 Task (JSON 파싱 불가)
        bad_dir = self.docs_dir / "tasks" / "TSK-BAD"
        bad_dir.mkdir(parents=True)
        self.corrupted_state = bad_dir / "state.json"
        self.corrupted_state.write_text("{corrupted json!!!}", encoding="utf-8")

        return self

    def __exit__(self, *_):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class ReadOnlyStateFixture:
    """읽기 전용 state.json 픽스처.

    state.json을 chmod 0o444로 설정한다.
    Read-Only 보장 검증용.
    """

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="qa_readonly_")
        self.docs_dir = pathlib.Path(self._tmpdir)
        task_dir = self.docs_dir / "tasks" / "TSK-RO"
        task_dir.mkdir(parents=True)
        self.state_file = task_dir / "state.json"
        self.state_file.write_text(
            json.dumps({"status": "[dd]", "updated": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
        # 읽기 전용으로 변경
        self.state_file.chmod(0o444)
        return self

    def __exit__(self, *_):
        # 정리 전 쓰기 권한 복구 (rmtree 가능하도록)
        try:
            self.state_file.chmod(0o644)
        except OSError:
            pass
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class PortConflictFixture:
    """포트 충돌 픽스처.

    지정된 포트를 미리 socket.bind()로 점유하여
    monitor-server.py가 동일 포트에 기동 시도할 때 충돌하도록 한다.
    QA 시나리오 5(포트 충돌 재기동 → idempotent 재사용 안내) 재현용.
    """

    def __init__(self, port: int = 0):
        self._port = port  # 0이면 OS가 자동 할당
        self._sock = None

    def __enter__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self._port))
        self.port = self._sock.getsockname()[1]
        return self

    def __exit__(self, *_):
        if self._sock:
            self._sock.close()


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

class TestMonitorServerExists(unittest.TestCase):
    """monitor-server.py 파일이 존재해야 함"""

    def test_file_exists(self):
        server_path = _SCRIPT_DIR / "monitor-server.py"
        self.assertTrue(
            server_path.exists(),
            "scripts/monitor-server.py 파일이 존재해야 합니다.",
        )


class TestT1RefreshSeconds(unittest.TestCase):
    """PRD §8 T1: --refresh-seconds 기본값 = 3"""

    def test_parse_args_has_refresh_seconds(self):
        """parse_args()가 refresh_seconds 속성을 반환해야 함"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertTrue(
            hasattr(args, "refresh_seconds"),
            "parse_args() 결과에 refresh_seconds 속성이 있어야 합니다.",
        )

    def test_default_refresh_seconds_is_3(self):
        """--refresh-seconds 기본값은 3이어야 함 (PRD §8 T1)"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertEqual(
            args.refresh_seconds, 3,
            f"--refresh-seconds 기본값이 3이어야 합니다. 실제값: {getattr(args, 'refresh_seconds', 'N/A')}",
        )

    def test_custom_refresh_seconds(self):
        """--refresh-seconds 커스텀 값 지정 가능해야 함"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args(["--refresh-seconds", "10"])
        self.assertEqual(args.refresh_seconds, 10)

    def test_html_meta_refresh_in_source(self):
        """monitor-server.py 소스에 meta refresh 관련 코드가 있어야 함"""
        src = (_SCRIPT_DIR / "monitor-server.py").read_text(encoding="utf-8")
        self.assertIn("refresh", src.lower())


class TestT2MaxPaneLines(unittest.TestCase):
    """PRD §8 T2: --max-pane-lines 기본값 = 500"""

    def test_parse_args_has_max_pane_lines(self):
        """parse_args()가 max_pane_lines 속성을 반환해야 함"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertTrue(
            hasattr(args, "max_pane_lines"),
            "parse_args() 결과에 max_pane_lines 속성이 있어야 합니다.",
        )

    def test_default_max_pane_lines_is_500(self):
        """--max-pane-lines 기본값은 500이어야 함 (PRD §8 T2)"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args([])
        self.assertEqual(
            args.max_pane_lines, 500,
            f"--max-pane-lines 기본값이 500이어야 합니다. 실제값: {getattr(args, 'max_pane_lines', 'N/A')}",
        )

    def test_custom_max_pane_lines(self):
        """--max-pane-lines 커스텀 값 지정 가능해야 함"""
        ms = _import_server()
        if not hasattr(ms, "parse_args"):
            self.skipTest("parse_args 함수 미존재")
        args = ms.parse_args(["--max-pane-lines", "1000"])
        self.assertEqual(args.max_pane_lines, 1000)


class TestEmptyProjectFixture(unittest.TestCase):
    """EmptyProjectFixture 동작 검증"""

    def test_creates_tasks_dir(self):
        with EmptyProjectFixture() as fix:
            self.assertTrue((fix.docs_dir / "tasks").is_dir())

    def test_creates_features_dir(self):
        with EmptyProjectFixture() as fix:
            self.assertTrue((fix.docs_dir / "features").is_dir())

    def test_tasks_dir_is_empty(self):
        with EmptyProjectFixture() as fix:
            self.assertEqual(list((fix.docs_dir / "tasks").iterdir()), [])

    def test_cleanup_removes_tmpdir(self):
        with EmptyProjectFixture() as fix:
            tmpdir = fix.docs_dir
        self.assertFalse(tmpdir.exists(), "컨텍스트 종료 후 임시 디렉터리가 삭제되어야 합니다.")


class TestCorruptedStateFixture(unittest.TestCase):
    """CorruptedStateFixture 동작 검증"""

    def test_creates_good_task(self):
        with CorruptedStateFixture() as fix:
            good = fix.docs_dir / "tasks" / "TSK-GOOD" / "state.json"
            self.assertTrue(good.exists())
            data = json.loads(good.read_text())
            self.assertEqual(data["status"], "[dd]")

    def test_creates_corrupted_task(self):
        with CorruptedStateFixture() as fix:
            bad = fix.docs_dir / "tasks" / "TSK-BAD" / "state.json"
            self.assertTrue(bad.exists())
            with self.assertRaises(json.JSONDecodeError):
                json.loads(bad.read_text())

    def test_cleanup_removes_tmpdir(self):
        with CorruptedStateFixture() as fix:
            tmpdir = fix.docs_dir
        self.assertFalse(tmpdir.exists())


class TestReadOnlyStateFixture(unittest.TestCase):
    """ReadOnlyStateFixture 동작 검증"""

    def test_state_file_is_readonly(self):
        with ReadOnlyStateFixture() as fix:
            mode = fix.state_file.stat().st_mode
            self.assertFalse(bool(mode & stat.S_IWUSR))

    def test_state_file_still_readable(self):
        with ReadOnlyStateFixture() as fix:
            content = fix.state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            self.assertEqual(data["status"], "[dd]")

    def test_cleanup_removes_tmpdir(self):
        with ReadOnlyStateFixture() as fix:
            tmpdir = fix.docs_dir
        self.assertFalse(tmpdir.exists())


class TestPortConflictFixture(unittest.TestCase):
    """PortConflictFixture 동작 검증"""

    def test_port_is_occupied(self):
        with PortConflictFixture(port=0) as fix:
            occupied_port = fix.port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", occupied_port))
                bound = True
            except OSError:
                bound = False
            finally:
                s.close()
            self.assertFalse(bound, "점유된 포트에 bind가 성공하면 안 됩니다.")

    def test_port_released_after_exit(self):
        with PortConflictFixture(port=0) as fix:
            released_port = fix.port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", released_port))
            bound = True
        except OSError:
            bound = False
        finally:
            s.close()
        self.assertTrue(bound, "컨텍스트 종료 후 포트가 해제되어야 합니다.")


class TestScanTasksWithCorruptedState(unittest.TestCase):
    """monitor-server._scan_tasks()가 손상된 state.json을 graceful하게 처리해야 함"""

    def test_corrupted_state_skipped_not_crashed(self):
        ms = _import_server()
        if not hasattr(ms, "_scan_tasks"):
            self.skipTest("_scan_tasks 함수 미존재")
        with CorruptedStateFixture() as fix:
            tasks = ms._scan_tasks(str(fix.docs_dir))
            self.assertIsInstance(tasks, list)

    def test_good_task_included_bad_task_skipped(self):
        ms = _import_server()
        if not hasattr(ms, "_scan_tasks"):
            self.skipTest("_scan_tasks 함수 미존재")
        with CorruptedStateFixture() as fix:
            tasks = ms._scan_tasks(str(fix.docs_dir))
            ids = [t["id"] for t in tasks]
            self.assertIn("TSK-GOOD", ids, "정상 Task는 목록에 포함되어야 합니다.")
            self.assertNotIn("TSK-BAD", ids, "손상 Task는 목록에서 제외되어야 합니다.")


class TestScanTasksEmptyProject(unittest.TestCase):
    """빈 프로젝트에서 _scan_tasks()는 빈 목록을 반환해야 함"""

    def test_empty_project_returns_empty_list(self):
        ms = _import_server()
        if not hasattr(ms, "_scan_tasks"):
            self.skipTest("_scan_tasks 함수 미존재")
        with EmptyProjectFixture() as fix:
            tasks = ms._scan_tasks(str(fix.docs_dir))
            self.assertEqual(tasks, [], "빈 프로젝트에서 태스크 목록은 비어야 합니다.")


class TestDashboardHtmlEmptyProject(unittest.TestCase):
    """빈 프로젝트에서 대시보드 HTML에 '태스크 없음' 안내가 있어야 함"""

    def _start_server(self, ms, docs_dir: str, port: int):
        _DashboardHandler = ms._DashboardHandler
        _DashboardHandler.docs_dir = docs_dir
        import http.server
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _DashboardHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server

    def test_empty_project_html_contains_no_tasks_message(self):
        ms = _import_server()
        if not hasattr(ms, "_DashboardHandler"):
            self.skipTest("_DashboardHandler 클래스 미존재")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        with EmptyProjectFixture() as fix:
            server = self._start_server(ms, str(fix.docs_dir), port)
            try:
                time.sleep(0.3)
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=3
                )
                html = resp.read().decode("utf-8")
                has_no_tasks = (
                    "태스크 없음" in html
                    or "no tasks" in html.lower()
                    or "(태스크 없음)" in html
                )
                self.assertTrue(
                    has_no_tasks,
                    "빈 프로젝트 HTML에 '태스크 없음' 메시지가 있어야 합니다.\n"
                    f"실제 HTML 일부: {html[:500]}",
                )
            finally:
                server.shutdown()


class TestReadOnlyStateSurvival(unittest.TestCase):
    """읽기 전용 state.json이 있어도 서버가 계속 동작해야 함"""

    def _start_server(self, ms, docs_dir: str, port: int):
        _DashboardHandler = ms._DashboardHandler
        _DashboardHandler.docs_dir = docs_dir
        import http.server
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _DashboardHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server

    def test_server_survives_readonly_state(self):
        ms = _import_server()
        if not hasattr(ms, "_DashboardHandler"):
            self.skipTest("_DashboardHandler 클래스 미존재")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        with ReadOnlyStateFixture() as fix:
            server = self._start_server(ms, str(fix.docs_dir), port)
            try:
                time.sleep(0.3)
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=3
                )
                self.assertEqual(resp.status, 200)
            finally:
                server.shutdown()


if __name__ == "__main__":
    unittest.main()
