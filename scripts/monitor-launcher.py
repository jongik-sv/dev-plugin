"""
monitor-launcher.py — dev-monitor 서버 기동/정지/상태 관리 헬퍼

사용법:
  python monitor-launcher.py [--port N] [--docs DIR] [--project-root DIR]
  python monitor-launcher.py --stop [--port N]
  python monitor-launcher.py --status [--port N]

기동 플로우:
  1. 프로젝트 PID 파일 존재 + os.kill(pid, 0) 생존 → URL 재출력 후 종료 (idempotent)
  2. --port 미지정 시 7321~7399 범위에서 자동 포트 탐색
  3. socket bind 테스트 → 실패 시 사용자 안내
  4. subprocess.Popen detach (macOS/Linux: start_new_session=True,
                              Windows: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
  5. JSON PID 파일 기록: {"pid": N, "port": N}
  6. http://localhost:{port} URL 출력
"""
import argparse
import hashlib
import json
import os
import pathlib
import signal
import socket
import subprocess
import sys
import tempfile

# 플랫폼 공통 상수 (_platform.py에서 IS_WINDOWS 가져오기)
_TEMP_DIR = pathlib.Path(tempfile.gettempdir())

try:
    from _platform import IS_WINDOWS  # type: ignore[import]
except ImportError:
    IS_WINDOWS = sys.platform == "win32"


def project_key(project_root: str) -> str:
    """프로젝트 루트 경로의 sha256 해시 앞 12자리를 반환.

    os.path.realpath()로 심볼릭 링크를 해소하여 정규화한다.
    동일 물리 경로 → 동일 해시, 다른 경로 → 충돌 가능성 < 1/4096².
    """
    real = os.path.realpath(project_root)
    return hashlib.sha256(real.encode()).hexdigest()[:12]


def pid_file_path(project_root: str) -> pathlib.Path:
    """프로젝트 기반 PID 파일 경로 반환: {TMPDIR}/dev-monitor-{project_hash}.pid"""
    return _TEMP_DIR / f"dev-monitor-{project_key(project_root)}.pid"


def log_file_path(project_root: str) -> pathlib.Path:
    """프로젝트 기반 로그 파일 경로 반환: {TMPDIR}/dev-monitor-{project_hash}.log"""
    return _TEMP_DIR / f"dev-monitor-{project_key(project_root)}.log"


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


def read_pid_record(pid_path: pathlib.Path):
    """PID 파일에서 레코드를 읽어 dict 반환.

    JSON 포맷: {"pid": N, "port": N} → {"pid": int, "port": int}
    레거시(정수만): N → {"pid": int, "port": None}
    파싱 실패 or 파일 없음: None
    """
    try:
        content = pid_path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        # JSON 파싱 시도
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "pid" in data:
                return {"pid": int(data["pid"]), "port": data.get("port")}
        except (json.JSONDecodeError, ValueError):
            pass
        # 레거시: 정수 텍스트
        try:
            return {"pid": int(content), "port": None}
        except ValueError:
            return None
    except (FileNotFoundError, OSError):
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


def find_free_port(start: int = 7321, end: int = 7399):
    """start~end 범위에서 test_port()로 첫 번째 사용 가능한 포트 반환.

    찾지 못하면 None.
    """
    for port in range(start, end + 1):
        if test_port(port):
            return port
    return None


def start_server(port: int, docs: str, project_root: str, no_tmux: bool = False) -> None:
    """
    monitor-server.py를 백그라운드 detach로 기동하고 JSON PID 파일을 기록.
    플랫폼 분기:
      - macOS/Linux: start_new_session=True
      - Windows psmux: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    sys.executable 사용 — python3 하드코딩 금지.

    Args:
        port: 서버 바인딩 포트
        docs: docs 디렉터리
        project_root: 프로젝트 루트 (PID/로그 파일 경로 계산용)
        no_tmux: True이면 --no-tmux 플래그를 monitor-server.py에 전달한다.
                 Team 섹션에 "tmux not available" 안내가 표시되며,
                 tmux 미설치 환경 시뮬레이션 또는 테스트 용도로 사용한다.
    """
    server_script = pathlib.Path(__file__).resolve().parent / "monitor-server.py"
    log_path = log_file_path(project_root)
    pid_path = pid_file_path(project_root)

    cmd = [
        sys.executable,
        str(server_script),
        "--port", str(port),
        "--docs", docs,
        "--project-root", project_root,
    ]
    if no_tmux:
        cmd.append("--no-tmux")

    with open(str(log_path), "a", encoding="utf-8") as log_fh:
        if IS_WINDOWS:
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

    # JSON PID 파일 기록 (open with newline="\n" — Windows CRLF 방지, Python 3.8 호환)
    with open(str(pid_path), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pid": proc.pid, "port": port}, f)


def _send_sigterm(pid: int, port_label: str) -> None:
    """pid에 SIGTERM(Unix) 또는 taskkill /F(Windows)를 보낸다.

    is_alive() 확인은 호출자 책임. OSError는 메시지 출력 후 반환.
    """
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False, timeout=3, shell=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"  dev-monitor ({port_label}): PID {pid} 종료 요청 완료.")
    except OSError as e:
        print(f"  dev-monitor ({port_label}): 종료 실패 — {e}")


def stop_server_by_project(project_root: str) -> None:
    """프로젝트 기준으로 실행 중인 서버를 종료. stop_server(project=...) 의 별칭."""
    stop_server(project=project_root)


def stop_server(*, project: "str | None" = None, port: "int | None" = None) -> None:
    """실행 중인 dev-monitor 서버를 SIGTERM으로 종료하고 PID 파일을 삭제.

    Args:
        project: 프로젝트 루트 경로 (프로젝트 기반 PID 파일 탐색)
        port: 포트 번호 (레거시 dev-monitor-{port}.pid 탐색)
        두 인자 모두 None이면 ValueError 발생.
    """
    if project is None and port is None:
        raise ValueError("stop_server: project 또는 port 중 하나를 지정해야 합니다.")

    if project is not None:
        # 프로젝트 기반 PID 파일 경로
        pid_path = pid_file_path(project)
        record = read_pid_record(pid_path)
        if record is None:
            print(f"  dev-monitor: PID 파일 없음 — 실행 중이지 않습니다.")
            return

        pid = record["pid"]
        _port = record.get("port")
        port_label = f"port {_port}" if _port else "unknown port"

        if is_alive(pid):
            _send_sigterm(pid, port_label)
        else:
            print(f"  dev-monitor ({port_label}): PID {pid} 프로세스가 이미 종료되어 있습니다.")

        if pid_path.exists():
            pid_path.unlink()
    else:
        # 레거시 포트 기반 PID 파일 경로 (하위호환)
        legacy_pid_path = _TEMP_DIR / f"dev-monitor-{port}.pid"
        if not legacy_pid_path.exists():
            print(f"  dev-monitor (port {port}): PID 파일 없음 — 실행 중이지 않습니다.")
            return

        record = read_pid_record(legacy_pid_path)
        pid = record["pid"] if record else None
        if pid is None:
            print(f"  dev-monitor (port {port}): PID 파일 파싱 실패.")
            return

        if is_alive(pid):
            _send_sigterm(pid, f"port {port}")
        else:
            print(f"  dev-monitor (port {port}): PID {pid} 프로세스가 이미 종료되어 있습니다.")
        legacy_pid_path.unlink(missing_ok=True)


def status_by_project(project_root: str) -> None:
    """프로젝트 기준으로 서버 실행 상태를 출력한다."""
    pid_path = pid_file_path(project_root)
    record = read_pid_record(pid_path)
    if record and is_alive(record["pid"]):
        port = record.get("port")
        pid = record["pid"]
        if port:
            print(f"  dev-monitor: running at http://localhost:{port} (PID {pid})")
        else:
            print(f"  dev-monitor: running (PID {pid}, port unknown)")
    else:
        print(f"  dev-monitor: not running")


def parse_args(argv=None):
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(
        description="dev-monitor 서버 기동/정지/상태 관리",
        add_help=True,
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="서버 포트 (기본: 자동 탐색 7321~7399)"
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
    parser.add_argument(
        "--no-tmux", action="store_true", default=False,
        dest="no_tmux",
        help="tmux 미설치 환경 시뮬레이션 — Team 섹션에 'tmux not available' 표시"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    project_root = args.project_root

    # --stop 서브커맨드
    if args.stop:
        if args.port is not None:
            # 포트 명시 → 레거시 stop_server (포트 기준)
            stop_server(port=args.port)
        else:
            # 포트 미지정 → 프로젝트 기준
            stop_server(project=project_root)
        return

    # --status 서브커맨드
    if args.status:
        if args.port is not None:
            # 포트 명시 → 레거시 방식 (포트 기준 PID 파일 우선 탐색 후 프로젝트 PID 파일)
            legacy_pid_path = _TEMP_DIR / f"dev-monitor-{args.port}.pid"
            if legacy_pid_path.exists():
                _rec = read_pid_record(legacy_pid_path)
                pid = _rec["pid"] if _rec else None
                if pid and is_alive(pid):
                    print(f"  dev-monitor: running at http://localhost:{args.port} (PID {pid})")
                else:
                    print(f"  dev-monitor: not running (port {args.port})")
            else:
                # 프로젝트 PID 파일에서 port 매칭 시도
                record = read_pid_record(pid_file_path(project_root))
                if record and record.get("port") == args.port and is_alive(record["pid"]):
                    print(f"  dev-monitor: running at http://localhost:{args.port} (PID {record['pid']})")
                else:
                    print(f"  dev-monitor: not running (port {args.port})")
        else:
            # 포트 미지정 → 프로젝트 기준
            status_by_project(project_root)
        return

    # 기동 플로우
    pid_path = pid_file_path(project_root)
    existing_record = read_pid_record(pid_path)

    # 1. PID 파일 존재 + 생존 → idempotent 재사용
    if existing_record and is_alive(existing_record["pid"]):
        existing_port = existing_record.get("port")
        print(f"  dev-monitor: 이미 실행 중입니다 (PID {existing_record['pid']})")
        if existing_port:
            print(f"  URL: http://localhost:{existing_port}")
        print(f"  (중복 기동 방지 — 새 프로세스 생성 안 함)")
        return

    # 좀비 PID 파일 정리: PID 파일은 있으나 프로세스가 이미 죽은 경우
    if existing_record is not None:
        pid_path.unlink(missing_ok=True)

    # 2. 포트 결정
    if args.port is not None:
        port = args.port
        # 포트 명시 시 socket bind 테스트
        if not test_port(port):
            print(f"  [오류] 포트 {port}이 이미 다른 프로세스에 의해 사용 중입니다.")
            print(f"  힌트: 다른 포트를 지정하려면 --port 옵션을 사용하세요.")
            print(f"  예: python monitor-launcher.py --port 7322")
            sys.exit(1)
    else:
        # 자동 포트 탐색
        port = find_free_port(7321, 7399)
        if port is None:
            print(f"  [오류] 7321~7399 범위의 포트가 모두 사용 중입니다.")
            print(f"  힌트: 명시적으로 --port 옵션으로 빈 포트를 지정하세요.")
            sys.exit(1)

    # 3 & 4. 서버 기동 + JSON PID 파일 기록
    start_server(port, args.docs, project_root, no_tmux=args.no_tmux)

    # 5. URL 출력
    print(f"  dev-monitor 기동 완료")
    print(f"  URL: http://localhost:{port}")
    print(f"  로그: {log_file_path(project_root)}")
    print(f"  PID 파일: {pid_file_path(project_root)}")


if __name__ == "__main__":
    main()
