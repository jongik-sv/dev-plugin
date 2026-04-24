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
    """pid_file_path 시그니처가 project_root(str)로 변경됨"""

    def test_returns_path_object(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertIsInstance(result, pathlib.Path)

    def test_filename_contains_project_hash(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        key = ml.project_key("/tmp/my-project")
        self.assertIn(key, result.name)

    def test_filename_pattern(self):
        ml = _import_launcher()
        key = ml.project_key("/tmp/test-proj")
        result = ml.pid_file_path("/tmp/test-proj")
        self.assertEqual(result.name, f"dev-monitor-{key}.pid")

    def test_is_in_temp_dir(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertEqual(result.parent, pathlib.Path(tempfile.gettempdir()))


class TestLogFilePath(unittest.TestCase):
    """log_file_path 시그니처가 project_root(str)로 변경됨"""

    def test_filename_pattern(self):
        ml = _import_launcher()
        key = ml.project_key("/tmp/test-proj")
        result = ml.log_file_path("/tmp/test-proj")
        self.assertEqual(result.name, f"dev-monitor-{key}.log")

    def test_is_in_temp_dir(self):
        ml = _import_launcher()
        result = ml.log_file_path("/tmp/my-project")
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
    """read_pid_record를 통해 PID 파일을 읽는 동작 검증"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            suffix=".pid", delete=False, mode="w"
        )
        self.tmp_path = pathlib.Path(self.tmp.name)

    def tearDown(self):
        if self.tmp_path.exists():
            self.tmp_path.unlink()

    def test_read_pid_wrapper_removed(self):
        """read_pid 래퍼 없이 read_pid_record를 직접 사용"""
        ml = _import_launcher()
        self.tmp.close()
        self.assertFalse(hasattr(ml, "read_pid"), "read_pid 래퍼가 삭제되지 않았습니다")

    def test_inline_replacement_reads_valid_pid_via_record(self):
        """정상 PID 파일에서 pid 값 반환"""
        ml = _import_launcher()
        self.tmp.write("12345\n")
        self.tmp.close()
        record = ml.read_pid_record(self.tmp_path)
        result = record["pid"] if record else None
        self.assertEqual(result, 12345)

    def test_inline_replacement_returns_none_for_nonexistent_file(self):
        ml = _import_launcher()
        self.tmp.close()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no_such_file_xyz.pid"
        record = ml.read_pid_record(nonexistent)
        result = record["pid"] if record else None
        self.assertIsNone(result)

    def test_inline_replacement_returns_none_for_invalid_content(self):
        ml = _import_launcher()
        self.tmp.write("not_a_number\n")
        self.tmp.close()
        record = ml.read_pid_record(self.tmp_path)
        result = record["pid"] if record else None
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
        import json as _json
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
        content = pid_path.read_text(encoding="utf-8").strip()
        record = _json.loads(content)
        self.assertEqual(record["pid"], 99999)
        self.assertEqual(record["port"], 7321)

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

    def test_is_windows_used_for_branch(self):
        """_platform.IS_WINDOWS 기반 분기를 사용해야 함 (sys.platform 인라인 대신)"""
        launcher_path = _SCRIPT_DIR / "monitor-launcher.py"
        if not launcher_path.exists():
            self.skipTest("monitor-launcher.py 미존재 (구현 전)")
        source = launcher_path.read_text()
        self.assertIn("IS_WINDOWS", source)

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
    """stop_server(project=...) / stop_server(port=...): SIGTERM + PID 파일 삭제 테스트"""

    def test_stop_by_project_removes_pid_file(self):
        """stop_server(project=...): 프로젝트 PID 파일 삭제 확인"""
        import json as _json
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-stop-{os.getpid()}.pid"
        tmp_pid.write_text(_json.dumps({"pid": os.getpid(), "port": 7321}), encoding="utf-8")

        with mock.patch("os.kill"), \
             mock.patch.object(ml, "pid_file_path", return_value=tmp_pid):
            ml.stop_server(project="/tmp/my-proj")

        self.assertFalse(tmp_pid.exists())

    def test_stop_no_pid_file_is_noop(self):
        ml = _import_launcher()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no-such-pid-xyz.pid"

        with mock.patch.object(ml, "pid_file_path", return_value=nonexistent):
            try:
                ml.stop_server(project="/tmp/no-proj")
            except Exception as e:
                self.fail(f"stop_server raised {e} unexpectedly")

    def test_stop_legacy_port_based_removes_pid_file(self):
        """stop_server(port=N): 레거시 dev-monitor-{port}.pid 삭제 확인"""
        ml = _import_launcher()
        port = 7391
        legacy_pid = ml._TEMP_DIR / f"dev-monitor-{port}.pid"
        legacy_pid.write_text(str(os.getpid()), encoding="utf-8")
        try:
            with mock.patch("os.kill"):
                ml.stop_server(port=port)
            self.assertFalse(legacy_pid.exists())
        finally:
            if legacy_pid.exists():
                legacy_pid.unlink()

    def test_stop_both_none_raises_value_error(self):
        """project와 port 모두 None이면 ValueError"""
        ml = _import_launcher()
        with self.assertRaises(ValueError):
            ml.stop_server()

    def test_stop_server_by_project_alias_works(self):
        """stop_server_by_project 별칭이 여전히 동작함을 확인"""
        import json as _json
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-alias-{os.getpid()}.pid"
        tmp_pid.write_text(_json.dumps({"pid": os.getpid(), "port": 7321}), encoding="utf-8")

        with mock.patch("os.kill"), \
             mock.patch.object(ml, "pid_file_path", return_value=tmp_pid):
            ml.stop_server_by_project("/tmp/my-proj")

        self.assertFalse(tmp_pid.exists())


class TestParseArgs(unittest.TestCase):
    """parse_args: 인자 파싱 테스트"""

    def test_default_port(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        # 새 동작: --port 미지정 시 None (자동 탐색)
        self.assertIsNone(args.port)

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


class TestProjectKey(unittest.TestCase):
    """project_key: sha256(realpath)[:12] 순수 함수 테스트"""

    def test_returns_12_char_hex(self):
        ml = _import_launcher()
        key = ml.project_key("/tmp/some-project")
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 12)
        # 모두 hex 문자여야 함
        int(key, 16)  # ValueError 없으면 통과

    def test_same_path_same_key(self):
        ml = _import_launcher()
        p = os.path.realpath(tempfile.gettempdir())
        self.assertEqual(ml.project_key(p), ml.project_key(p))

    def test_different_path_different_key(self):
        ml = _import_launcher()
        k1 = ml.project_key("/tmp/project-a")
        k2 = ml.project_key("/tmp/project-b")
        self.assertNotEqual(k1, k2)

    def test_realpath_normalization(self):
        """realpath로 정규화되므로 같은 실제 경로이면 동일 키 반환"""
        ml = _import_launcher()
        real = os.path.realpath(tempfile.gettempdir())
        # gettempdir()이 이미 realpath와 같다면 동일 키
        self.assertEqual(ml.project_key(real), ml.project_key(tempfile.gettempdir()))


class TestPidFilePathProjectBased(unittest.TestCase):
    """pid_file_path(project_root) 시그니처 변경 테스트"""

    def test_returns_path_object(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertIsInstance(result, pathlib.Path)

    def test_filename_uses_project_hash_not_port(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        # 파일명에 포트 숫자(7321 등)가 아닌 12자리 hex 해시가 포함되어야 함
        key = ml.project_key("/tmp/my-project")
        self.assertIn(key, result.name)

    def test_filename_has_pid_extension(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertTrue(result.name.endswith(".pid"))

    def test_filename_starts_with_dev_monitor(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertTrue(result.name.startswith("dev-monitor-"))

    def test_is_in_temp_dir(self):
        ml = _import_launcher()
        result = ml.pid_file_path("/tmp/my-project")
        self.assertEqual(result.parent, pathlib.Path(tempfile.gettempdir()))

    def test_different_projects_different_paths(self):
        ml = _import_launcher()
        p1 = ml.pid_file_path("/tmp/proj-a")
        p2 = ml.pid_file_path("/tmp/proj-b")
        self.assertNotEqual(p1, p2)


class TestLogFilePathProjectBased(unittest.TestCase):
    """log_file_path(project_root) 시그니처 변경 테스트"""

    def test_returns_path_object(self):
        ml = _import_launcher()
        result = ml.log_file_path("/tmp/my-project")
        self.assertIsInstance(result, pathlib.Path)

    def test_filename_uses_project_hash(self):
        ml = _import_launcher()
        key = ml.project_key("/tmp/my-project")
        result = ml.log_file_path("/tmp/my-project")
        self.assertIn(key, result.name)

    def test_filename_has_log_extension(self):
        ml = _import_launcher()
        result = ml.log_file_path("/tmp/my-project")
        self.assertTrue(result.name.endswith(".log"))


class TestReadPidRecord(unittest.TestCase):
    """read_pid_record: JSON PID 파일 + 레거시 정수 폴백 테스트"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            suffix=".pid", delete=False, mode="w", encoding="utf-8"
        )
        self.tmp_path = pathlib.Path(self.tmp.name)

    def tearDown(self):
        if self.tmp_path.exists():
            self.tmp_path.unlink()

    def test_reads_json_pid_record(self):
        ml = _import_launcher()
        import json
        self.tmp.write(json.dumps({"pid": 12345, "port": 7321}))
        self.tmp.close()
        result = ml.read_pid_record(self.tmp_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["pid"], 12345)
        self.assertEqual(result["port"], 7321)

    def test_reads_legacy_integer_pid(self):
        ml = _import_launcher()
        self.tmp.write("12345\n")
        self.tmp.close()
        result = ml.read_pid_record(self.tmp_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["pid"], 12345)
        self.assertIsNone(result["port"])

    def test_returns_none_for_nonexistent_file(self):
        ml = _import_launcher()
        self.tmp.close()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no_such_record_xyz.pid"
        result = ml.read_pid_record(nonexistent)
        self.assertIsNone(result)

    def test_returns_none_for_invalid_content(self):
        ml = _import_launcher()
        self.tmp.write("not_json_not_int\n")
        self.tmp.close()
        result = ml.read_pid_record(self.tmp_path)
        self.assertIsNone(result)

    def test_returns_none_for_empty_file(self):
        ml = _import_launcher()
        self.tmp.close()
        result = ml.read_pid_record(self.tmp_path)
        self.assertIsNone(result)


class TestFindFreePort(unittest.TestCase):
    """find_free_port: 7321~7399 범위 자동 탐색 테스트"""

    def test_returns_integer_in_range(self):
        ml = _import_launcher()
        port = ml.find_free_port(7321, 7399)
        if port is not None:  # 전부 점유된 경우는 None 허용
            self.assertGreaterEqual(port, 7321)
            self.assertLessEqual(port, 7399)

    def test_returned_port_is_actually_free(self):
        ml = _import_launcher()
        port = ml.find_free_port(7321, 7399)
        if port is not None:
            self.assertTrue(ml.test_port(port))

    def test_returns_none_when_all_occupied(self):
        """모든 포트가 점유되면 None 반환"""
        ml = _import_launcher()
        with mock.patch.object(ml, "test_port", return_value=False):
            result = ml.find_free_port(7321, 7323)
            self.assertIsNone(result)

    def test_skips_occupied_and_returns_next_free(self):
        """7321이 점유 → 7322 반환"""
        ml = _import_launcher()
        call_count = {"n": 0}
        def fake_test_port(p):
            call_count["n"] += 1
            return p != 7321  # 7321만 점유
        with mock.patch.object(ml, "test_port", side_effect=fake_test_port):
            result = ml.find_free_port(7321, 7325)
            self.assertEqual(result, 7322)


class TestJsonPidFileWrite(unittest.TestCase):
    """start_server가 JSON PID 파일을 기록하는지 테스트"""

    def _make_tmp_pid_path(self):
        return pathlib.Path(tempfile.gettempdir()) / f"test-proj-pid-{os.getpid()}.pid"

    def tearDown(self):
        pid_path = self._make_tmp_pid_path()
        if pid_path.exists():
            pid_path.unlink()
        log_path = pathlib.Path(tempfile.gettempdir()) / f"test-proj-{os.getpid()}.log"
        if log_path.exists():
            log_path.unlink()

    def test_pid_file_is_json_with_pid_and_port(self):
        import json
        ml = _import_launcher()
        pid_path = self._make_tmp_pid_path()
        log_path = pathlib.Path(tempfile.gettempdir()) / f"test-proj-{os.getpid()}.log"

        with mock.patch.object(ml, "pid_file_path", return_value=pid_path), \
             mock.patch.object(ml, "log_file_path", return_value=log_path), \
             mock.patch("subprocess.Popen") as mock_popen:
            mock_proc = mock.MagicMock()
            mock_proc.pid = 88888
            mock_popen.return_value = mock_proc
            ml.start_server(7350, "docs", str(pathlib.Path(__file__).parent.parent))

        self.assertTrue(pid_path.exists())
        content = pid_path.read_text(encoding="utf-8").strip()
        record = json.loads(content)
        self.assertEqual(record["pid"], 88888)
        self.assertEqual(record["port"], 7350)


class TestIdempotentStartWithProjectPid(unittest.TestCase):
    """같은 project_root 재기동 시 idempotent (JSON PID 파일 기반)"""

    def test_idempotent_start_reuses_existing_pid(self):
        """PID 파일 존재 + 생존 시 새 프로세스를 시작하지 않음"""
        import json
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-idemp-{os.getpid()}.pid"
        tmp_pid.write_text(
            json.dumps({"pid": os.getpid(), "port": 7321}), encoding="utf-8"
        )
        try:
            with mock.patch.object(ml, "pid_file_path", return_value=tmp_pid), \
                 mock.patch("subprocess.Popen") as mock_popen, \
                 mock.patch("sys.stdout"):
                ml.main(["--project-root", "/tmp/my-proj"])
            mock_popen.assert_not_called()
        finally:
            if tmp_pid.exists():
                tmp_pid.unlink()


class TestStopServerProjectBased(unittest.TestCase):
    """--stop 포트 미지정 → 프로젝트 PID 파일에서 port 읽어 종료"""

    def test_stop_without_port_reads_project_pid(self):
        import json
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-stop-proj-{os.getpid()}.pid"
        tmp_pid.write_text(
            json.dumps({"pid": os.getpid(), "port": 7321}), encoding="utf-8"
        )
        try:
            with mock.patch.object(ml, "pid_file_path", return_value=tmp_pid), \
                 mock.patch("os.kill") as mock_kill:
                ml.stop_server_by_project("/tmp/my-proj")
            mock_kill.assert_called()
        finally:
            if tmp_pid.exists():
                tmp_pid.unlink()

    def test_stop_removes_project_pid_file(self):
        import json
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-stop-rm-{os.getpid()}.pid"
        tmp_pid.write_text(
            json.dumps({"pid": os.getpid(), "port": 7321}), encoding="utf-8"
        )
        with mock.patch.object(ml, "pid_file_path", return_value=tmp_pid), \
             mock.patch("os.kill"):
            ml.stop_server_by_project("/tmp/my-proj")
        self.assertFalse(tmp_pid.exists())


class TestStatusProjectBased(unittest.TestCase):
    """--status 포트 미지정 → 프로젝트 PID 파일에서 port 읽어 출력"""

    def test_status_running_shows_port(self):
        import json, io
        ml = _import_launcher()
        tmp_pid = pathlib.Path(tempfile.gettempdir()) / f"test-stat-{os.getpid()}.pid"
        tmp_pid.write_text(
            json.dumps({"pid": os.getpid(), "port": 7345}), encoding="utf-8"
        )
        try:
            buf = io.StringIO()
            with mock.patch.object(ml, "pid_file_path", return_value=tmp_pid), \
                 mock.patch("sys.stdout", buf):
                ml.status_by_project("/tmp/my-proj")
            output = buf.getvalue()
            self.assertIn("7345", output)
            self.assertIn("running", output.lower())
        finally:
            if tmp_pid.exists():
                tmp_pid.unlink()

    def test_status_not_running_shows_not_running(self):
        import io
        ml = _import_launcher()
        nonexistent = pathlib.Path(tempfile.gettempdir()) / "no-proj-pid-xyz.pid"
        buf = io.StringIO()
        with mock.patch.object(ml, "pid_file_path", return_value=nonexistent), \
             mock.patch("sys.stdout", buf):
            ml.status_by_project("/tmp/no-proj")
        output = buf.getvalue()
        self.assertIn("not running", output.lower())


class TestParseArgsPortOptional(unittest.TestCase):
    """--port는 이제 선택사항 (미지정 시 None → 자동 탐색)"""

    def test_port_default_is_none(self):
        ml = _import_launcher()
        args = ml.parse_args(["--project-root", "/tmp"])
        # 새 동작: --port 미지정 시 None (자동 탐색)
        self.assertIsNone(args.port)

    def test_explicit_port_is_preserved(self):
        ml = _import_launcher()
        args = ml.parse_args(["--port", "7350", "--project-root", "/tmp"])
        self.assertEqual(args.port, 7350)


class TestSkillMdProjectBased(unittest.TestCase):
    """SKILL.md가 프로젝트 기반 동작을 설명하는지 확인"""

    def _read_skill_md(self):
        path = pathlib.Path(__file__).parent.parent / "skills" / "dev-monitor" / "SKILL.md"
        if not path.exists():
            self.skipTest("SKILL.md 미존재")
        return path.read_text()

    def test_stop_status_mention_project_based(self):
        """--stop/--status 설명에 '프로젝트' 또는 'project' 키워드가 있어야 함"""
        content = self._read_skill_md()
        self.assertTrue(
            "프로젝트" in content or "project" in content.lower(),
            "SKILL.md에 프로젝트 기반 동작 설명이 없습니다"
        )


if __name__ == "__main__":
    unittest.main()
