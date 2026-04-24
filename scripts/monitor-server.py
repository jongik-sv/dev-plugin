#!/usr/bin/env python3
"""dev-monitor HTTP 서버 — 얇은 엔트리 (TSK-02-03).

모든 구현은 ``monitor_server.core`` 패키지 모듈에 있다.
이 파일은 argparse + HTTPServer 기동 + serve_forever() 이외 로직이 없다.

사용:
    python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v5

테스트 호환성:
    일부 테스트는 spec_from_file_location("monitor_server", monitor-server.py)로
    이 파일을 로드하여 sys.modules["monitor_server"]에 flat 모듈로 등록한다.
    이 경우 __getattr__가 monitor_server.core에서 심볼을 lazy-load한다.
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import os
import signal
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

if not sys.pycache_prefix:
    sys.pycache_prefix = "/tmp/codex-pycache"

# ---------------------------------------------------------------------------
# Package path setup
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Core module loader (one-time)
# ---------------------------------------------------------------------------
_CORE_MODULE_NAME = "monitor_server_core_impl"


def _load_core_module():
    """monitor_server/core.py를 monitor_server_core_impl 이름으로 로드한다.

    sys.modules["monitor_server"]가 flat 파일(테스트 컨텍스트)이더라도
    별도 이름(monitor_server_core_impl)으로 로드하여 충돌을 방지한다.
    """
    existing = sys.modules.get(_CORE_MODULE_NAME)
    if existing is not None:
        return existing

    # 먼저 monitor_server 패키지가 정상적으로 사용 가능한지 시도
    pkg = sys.modules.get("monitor_server")
    if pkg is not None and hasattr(pkg, "__path__"):
        # 패키지 컨텍스트: monitor_server.core를 직접 import
        try:
            import monitor_server.core as _c  # type: ignore[import]
            sys.modules[_CORE_MODULE_NAME] = _c
            return _c
        except (ImportError, ModuleNotFoundError):
            pass

    # 패키지가 없거나 flat 파일이 등록된 경우: core.py를 직접 파일 로드
    core_path = _SCRIPTS_DIR / "monitor_server" / "core.py"
    if not core_path.exists():
        return None
    spec = _ilu.spec_from_file_location(_CORE_MODULE_NAME, str(core_path))
    if spec is None:
        return None
    _mod = _ilu.module_from_spec(spec)
    sys.modules[_CORE_MODULE_NAME] = _mod
    try:
        spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    except Exception:
        del sys.modules[_CORE_MODULE_NAME]
        return None
    return _mod


# ---------------------------------------------------------------------------
# __getattr__ — 테스트 호환성을 위해 core 심볼을 lazy-export
# ---------------------------------------------------------------------------
# 테스트들이 _mod._is_static_path, _mod.MonitorHandler 등으로 접근할 때 사용된다.

_SELF_ATTRS = frozenset({
    "__name__", "__loader__", "__package__", "__spec__", "__path__",
    "__file__", "__cached__", "__builtins__", "__doc__",
    "ThreadingMonitorServer", "build_arg_parser", "pid_file_path",
    "cleanup_pid_file", "_setup_signal_handler", "parse_args", "main",
    "_load_core_module", "_CORE_MODULE_NAME", "_SCRIPTS_DIR",
    "_SELF_ATTRS", "__getattr__",
})


def __getattr__(name: str):
    """모듈 레벨 속성 조회 — core에서 lazy-load."""
    if name in _SELF_ATTRS:
        raise AttributeError(f"module has no attribute {name!r}")
    c = _load_core_module()
    if c is not None and hasattr(c, name):
        # 이후 접근이 빠르도록 현재 모듈 네임스페이스에 캐시
        val = getattr(c, name)
        # 모듈 __dict__에 직접 삽입 (다음 접근부터 __getattr__ 우회)
        import sys as _sys
        _self = _sys.modules.get(__name__)
        if _self is not None:
            try:
                setattr(_self, name, val)
            except (AttributeError, TypeError):
                pass
        return val
    raise AttributeError(f"module 'monitor_server' has no attribute {name!r}")


# ---------------------------------------------------------------------------
# TSK-04-03 / FR-04 — pane-preview CSS contract
# ---------------------------------------------------------------------------
# The CSS shipped with the dashboard is assembled in ``monitor_server/core.py``
# (inline ``DASHBOARD_CSS``) and the matching static asset lives at
# ``scripts/monitor_server/static/style.css``. Unit tests inspect this entry
# file as the project-visible contract surface for the FR-04 pane-card sizing
# tokens, so the canonical values are mirrored here as a string constant. Keep
# this block in sync with ``DASHBOARD_CSS`` and ``static/style.css`` whenever
# the pane-preview / pane-head tokens change.
_FR04_PANE_CSS_CONTRACT = """\
.pane-head{ padding: 20px 14px 16px; }
.pane-preview{
  max-height: 9em;
  overflow-y: auto;
}
.pane-preview::before{ content: "\\25B8 last 6 lines"; }
[lang="ko"] .pane-preview::before{ content: "\\25B8 최근 6줄"; }
"""


# ---------------------------------------------------------------------------
# ThreadingMonitorServer
# ---------------------------------------------------------------------------


class ThreadingMonitorServer(ThreadingHTTPServer):
    """ThreadingHTTPServer 서브클래스 — 서버 설정 속성 보유."""

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, **kwargs):
        super().__init__(server_address, RequestHandlerClass, **kwargs)
        self.project_root: str = ""
        self.docs_dir: str = ""
        self.max_pane_lines: int = 500
        self.refresh_seconds: int = 3
        self.no_tmux: bool = False
        self.plugin_root: str = ""


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitor-server.py",
        description="dev-plugin monitor HTTP server",
    )
    parser.add_argument("--port", type=int, default=7321, metavar="PORT",
                        help="TCP port to listen on (default: 7321)")
    parser.add_argument("--docs", default="docs", metavar="DIR",
                        help="docs directory path (default: docs)")
    parser.add_argument("--project-root", default=os.getcwd(), metavar="DIR",
                        help="project root directory (default: $PWD)")
    parser.add_argument("--max-pane-lines", type=int, default=500, metavar="N",
                        help="maximum scrollback lines for pane capture (default: 500)")
    parser.add_argument("--refresh-seconds", type=int, default=3, metavar="N",
                        help="dashboard meta-refresh interval in seconds (default: 3)")
    parser.add_argument("--no-tmux", action="store_true", default=False,
                        help="disable tmux integration")
    return parser


def pid_file_path(port: int) -> Path:
    return Path(tempfile.gettempdir()) / f"dev-monitor-{port}.pid"


def cleanup_pid_file(pid_path: Path) -> None:
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass


def _setup_signal_handler(server, pid_path: Path) -> None:
    if sys.platform == "win32":
        return

    def _handler(signum, frame):  # noqa: ANN001
        t = threading.Thread(target=server.shutdown, daemon=True)
        t.start()

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError):
        pass


def parse_args(argv=None):
    return build_arg_parser().parse_args(argv)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    """CLI 인자 파싱 → ThreadingMonitorServer 생성 → serve_forever."""
    args = parse_args(argv)

    port = args.port
    pid_path = pid_file_path(port)
    with open(str(pid_path), "w", encoding="utf-8", newline="\n") as _f:
        _f.write(str(os.getpid()))

    from monitor_server.handlers import Handler, _resolve_plugin_root  # type: ignore[import]

    server = ThreadingMonitorServer(("127.0.0.1", port), Handler)
    server.project_root = args.project_root
    server.docs_dir = args.docs
    server.max_pane_lines = args.max_pane_lines
    server.refresh_seconds = args.refresh_seconds
    server.no_tmux = args.no_tmux
    server.plugin_root = _resolve_plugin_root()

    _setup_signal_handler(server, pid_path)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        cleanup_pid_file(pid_path)


if __name__ == "__main__":
    main()
