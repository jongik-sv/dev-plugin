"""monitor_server.renderers.taskrow — phase/task-row 공용 헬퍼.

TSK-02-01:
- 커밋 1 시점 (선-shim): monitor-server.py의 함수를 _util 경유로 재-export.
  wp.py / depgraph.py 가 커밋 1~5 기간 동안 이 모듈에서 import할 수 있도록 선행 생성.
- 커밋 6 시점 (본문 이전): 함수 본문을 monitor-server.py에서 복사하고
  monitor-server.py의 원본은 shim 라인으로 대체.

현재 상태: 선-shim (커밋 1).
"""

from __future__ import annotations

try:
    from ._util import _mod as _entry  # type: ignore[attr-defined]
except ImportError:
    # Standalone load (spec_from_file_location without package linkage).
    # Resolve _util.py by absolute path so `_entry` stays bound.
    import importlib.util as _ilu
    import pathlib as _pl
    import sys as _sys

    _here = _pl.Path(__file__).resolve().parent
    # Make scripts/ importable so `from monitor_server import core` inside
    # _util.py can resolve the real package.
    _scripts_dir = _here.parent.parent
    if str(_scripts_dir) not in _sys.path:
        _sys.path.insert(0, str(_scripts_dir))
    # Purge any flat `monitor_server` entry (monitor-server.py loaded via
    # spec_from_file_location in other tests) so `from monitor_server import
    # core` binds to the real package.
    _existing = _sys.modules.get("monitor_server")
    if _existing is not None and not hasattr(_existing, "__path__"):
        del _sys.modules["monitor_server"]
    _spec = _ilu.spec_from_file_location(
        "monitor_server_renderers_util_standalone",
        _here / "_util.py",
    )
    _u = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_u)  # type: ignore[union-attr]
    _entry = _u._mod

# 선-shim: monitor-server.py의 원본 함수를 그대로 재-export
_phase_label = _entry._phase_label
_phase_data_attr = _entry._phase_data_attr
_trow_data_status = _entry._trow_data_status
_render_task_row_v2 = _entry._render_task_row_v2
