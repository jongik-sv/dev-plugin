"""
monitor-launcher.py — dev-monitor 서버 기동/정지/상태 관리 헬퍼

사용법:
  python monitor-launcher.py [--port N] [--docs DIR] [--project-root DIR]
  python monitor-launcher.py --stop [--port N]
  python monitor-launcher.py --status [--port N]

기동 플로우:
  1. PID 파일 존재 + os.kill(pid, 0) 생존 → URL 재출력 후 종료 (idempotent)
  2. socket bind 테스트 → 실패 시 사용자 안내
  3. subprocess.Popen detach (macOS/Linux: start_new_session=True,
                              Windows: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
  4. PID 파일 기록
  5. http://localhost:{port} URL 출력
"""
import argparse
import os
import pathlib
import signal
import socket
import subprocess
import sys
import tempfile

# 플랫폼 공통 TEMP_DIR
_TEMP_DIR = pathlib.Path(tempfile.gettempdir())


def _temp_path(port: int, ext: str) -> pathlib.Path:
    """내부 헬퍼: {TMPDIR}/dev-monitor-{port}.{ext} 경로 반환."""
    return _TEMP_DIR / f"dev-monitor-{port}.{ext}"


def pid_file_path(port: int) -> pathlib.Path:
    """PID 파일 경로 반환: {TMPDIR}/dev-monitor-{port}.pid"""
    return _temp_path(port, "pid")


def log_file_path(port: int) -> pathlib.Path:
    """로그 파일 경로 반환: {TMPDIR}/dev-monitor-{port}.log"""
    return _temp_path(port, "log")


def is_alive(pid: int) -> bool:
    """os.kill(pid, 0)으로 프로세스 생존 여부 확인."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        # ProcessLookupError / PermissionError 등 OSError 계열 전부 → 비생존 처리
        return False


def read_pid(pid_path: pathlib.Path):
    """PID 파일에서 정수 PID를 읽어 반환. 없거나 파싱 불가면 None."""
    try:
        content = pid_path.read_text().strip()
        return int(content)
    except (FileNotFoundError, ValueError, OSError):
        return None


def test_port(port: int) -> bool:
    """127.0.0.1:{port}에 bind 테스트. 사용 가능하면 True, 점유 중이면 False.

    SO_REUSEADDR를 의도적으로 설정하지 않는다 — 포트가 TIME_WAIT 상태이더라도
    "이미 사용 중"으로 판단하여 사용자에게 안내하기 위함이다.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start_server(port: int, docs: str, project_root: str) -> None:
    """
    monitor-server.py를 백그라운드 detach로 기동하고 PID 파일을 기록.
    플랫폼 분기:
      - macOS/Linux: start_new_session=True
      - Windows psmux: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    sys.executable 사용 — python3 하드코딩 금지.
    """
    server_script = pathlib.Path(project_root) / "scripts" / "monitor-server.py"
    log_path = log_file_path(port)
    pid_path = pid_file_path(port)

    cmd = [
        sys.executable,
        str(server_script),
        "--port", str(port),
        "--docs", docs,
    ]

    with open(str(log_path), "a", encoding="utf-8") as log_fh:
        if sys.platform == "win32":
            DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            CREATE_NEW_PROCESS_GROUP = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
            )
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
                cwd=project_root,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
                cwd=project_root,
                start_new_session=True,
                close_fds=True,
            )

    # PID 파일 기록 (open with newline="\n" — Windows CRLF 방지, Python 3.8 호환)
    with open(str(pid_path), "w", encoding="utf-8", newline="\n") as f:
        f.write(str(proc.pid))


def stop_server(port: int) -> None:
    """실행 중인 서버를 SIGTERM으로 종료하고 PID 파일을 삭제."""
    pid_path = pid_file_path(port)
    pid = read_pid(pid_path)
    if pid is None:
        print(f"  dev-monitor (port {port}): PID 파일 없음 — 실행 중이지 않습니다.")
        return

    if is_alive(pid):
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    check=False, timeout=3, shell=False,
                )
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"  dev-monitor (port {port}): PID {pid} 종료 요청 완료.")
        except OSError as e:
            print(f"  dev-monitor (port {port}): 종료 실패 — {e}")
    else:
        print(f"  dev-monitor (port {port}): PID {pid} 프로세스가 이미 종료되어 있습니다.")

    if pid_path.exists():
        pid_path.unlink()


def parse_args(argv=None):
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(
        description="dev-monitor 서버 기동/정지/상태 관리",
        add_help=True,
    )
    parser.add_argument(
        "--port", type=int, default=7321,
        help="서버 포트 (기본: 7321)"
    )
    parser.add_argument(
        "--docs", type=str, default="docs",
        help="대시보드가 스캔할 docs 디렉터리 (기본: docs)"
    )
    parser.add_argument(
        "--project-root", type=str, default=os.getcwd(),
        dest="project_root",
        help="프로젝트 루트 경로 (기본: 현재 디렉터리)"
    )
    parser.add_argument(
        "--stop", action="store_true", default=False,
        help="실행 중인 서버를 종료"
    )
    parser.add_argument(
        "--status", action="store_true", default=False,
        help="서버 실행 상태 확인"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    port = args.port

    # --stop 서브커맨드
    if args.stop:
        stop_server(port)
        return

    # --status 서브커맨드
    if args.status:
        pid = read_pid(pid_file_path(port))
        if pid and is_alive(pid):
            print(f"  dev-monitor: running at http://localhost:{port} (PID {pid})")
        else:
            print(f"  dev-monitor: not running (port {port})")
        return

    # 기동 플로우
    pid_path = pid_file_path(port)
    existing_pid = read_pid(pid_path)

    # 1. PID 파일 존재 + 생존 → idempotent 재사용
    if existing_pid and is_alive(existing_pid):
        print(f"  dev-monitor: 이미 실행 중입니다 (PID {existing_pid})")
        print(f"  URL: http://localhost:{port}")
        print(f"  (중복 기동 방지 — 새 프로세스 생성 안 함)")
        return

    # 좀비 PID 파일 정리: PID 파일은 있으나 프로세스가 이미 죽은 경우
    if existing_pid is not None:
        pid_path.unlink(missing_ok=True)

    # 2. socket bind 테스트
    if not test_port(port):
        print(f"  [오류] 포트 {port}이 이미 다른 프로세스에 의해 사용 중입니다.")
        print(f"  힌트: 다른 포트를 지정하려면 --port 옵션을 사용하세요.")
        print(f"  예: python monitor-launcher.py --port 7322")
        sys.exit(1)

    # 3 & 4. 서버 기동 + PID 파일 기록
    start_server(port, args.docs, args.project_root)

    # 5. URL 출력
    print(f"  dev-monitor 기동 완료")
    print(f"  URL: http://localhost:{port}")
    print(f"  로그: {log_file_path(port)}")
    print(f"  PID 파일: {pid_file_path(port)}")


if __name__ == "__main__":
    main()
