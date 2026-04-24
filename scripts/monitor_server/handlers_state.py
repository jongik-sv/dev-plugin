"""monitor_server.handlers_state — /api/state HTTP handler.

[core-http-split:C1-3]

Migrated from core.py:
  _handle_api_state  (was L6362–L6484)

순환 참조 회피: core.py를 직접 import하지 않는다.
  - workitems, signals, panes 는 모듈 레벨 로드 (flat-load 호환 try/except).
  - core 경유 심볼은 함수 내부에서 _resolve_core() 지연 접근.

테스트 패치 호환:
  테스트가 mock.patch.object(this_module, "discover_subprojects", ...) 으로
  패치할 수 있도록 discover_subprojects 등은 모듈 레벨 변수로 노출한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from monitor_server.panes import PaneInfo
    from monitor_server.signals import SignalEntry
    from monitor_server.workitems import WorkItem


# ---------------------------------------------------------------------------
# Internal: core module resolver (flat-load compatible)
# ---------------------------------------------------------------------------

def _resolve_core():
    """monitor_server.core를 반환한다 (flat-load 컨텍스트 호환).

    우선순위: monitor_server_core_impl → monitor_server.core → 패키지 import → 파일 load.
    monitor_server_core_impl을 먼저 확인: 테스트 mock.patch.object 패치 대상과 동일 객체 보장.
    """
    c = sys.modules.get("monitor_server_core_impl")
    if c is not None:
        return c
    c = sys.modules.get("monitor_server.core")
    if c is not None:
        return c
    try:
        import monitor_server.core as _c  # type: ignore[import]
        return _c
    except (ImportError, ModuleNotFoundError):
        pass
    import importlib.util
    _pkg = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("monitor_server_core_impl", str(_pkg / "core.py"))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_core_impl"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Module-level symbol loading (flat-load compatible)
# workitems / signals / panes 심볼을 모듈 레벨에 노출하여 테스트 패치 가능하게 함.
# ---------------------------------------------------------------------------

def _load_workitem_syms():
    """workitems 심볼을 패키지 import → flat-load fallback 순으로 로드."""
    try:
        from monitor_server.workitems import (  # type: ignore[import]
            scan_tasks as _st,
            scan_features as _sf,
            discover_subprojects as _ds,
            _dedup_workitems_by_id as _dd,
            _aggregated_scan as _ag,
        )
        return _st, _sf, _ds, _dd, _ag
    except (ImportError, ModuleNotFoundError):
        pass
    _core = _resolve_core()
    if _core is not None:
        return (
            getattr(_core, "scan_tasks", None),
            getattr(_core, "scan_features", None),
            getattr(_core, "discover_subprojects", None),
            getattr(_core, "_dedup_workitems_by_id", None),
            getattr(_core, "_aggregated_scan", None),
        )
    return None, None, None, None, None


def _load_signal_sym():
    try:
        from monitor_server.signals import scan_signals as _ss  # type: ignore[import]
        return _ss
    except (ImportError, ModuleNotFoundError):
        pass
    _core = _resolve_core()
    return getattr(_core, "scan_signals", None) if _core else None


def _load_pane_sym():
    try:
        from monitor_server.panes import list_tmux_panes as _lp  # type: ignore[import]
        return _lp
    except (ImportError, ModuleNotFoundError):
        pass
    _core = _resolve_core()
    return getattr(_core, "list_tmux_panes", None) if _core else None


# 모듈 레벨 defaults — 테스트에서 mock.patch.object(this_module, "discover_subprojects", ...)
# 형태로 교체 가능하다.
_st, _sf, _ds, _dd, _ag = _load_workitem_syms()
scan_tasks = _st
scan_features = _sf
discover_subprojects = _ds
_dedup_workitems_by_id = _dd
_aggregated_scan = _ag
scan_signals = _load_signal_sym()
list_tmux_panes = _load_pane_sym()


# ---------------------------------------------------------------------------
# Handler function
# ---------------------------------------------------------------------------


def _handle_api_state(
    handler,
    *,
    scan_tasks: "Optional[Callable[[Any], List[WorkItem]]]" = None,
    scan_features: "Optional[Callable[[Any], List[WorkItem]]]" = None,
    scan_signals: "Optional[Callable[[], List[SignalEntry]]]" = None,
    list_tmux_panes: "Optional[Callable[[], Optional[List[PaneInfo]]]]" = None,
) -> None:
    """Handle ``GET /api/state`` on *handler*.

    Migrated from core.py _handle_api_state.
    순환 참조 회피: core 심볼은 _resolve_core() 지연 접근.
    flat-load 호환: 모듈 레벨 workitem 심볼 사용.
    테스트 패치: 모듈 레벨 discover_subprojects 등을 globals()로 참조.
    """
    _core = _resolve_core()

    # 파라미터 기본값: 모듈 레벨 변수 경유 (테스트 패치 반영을 위해 globals() 사용)
    _g = globals()
    if scan_tasks is None:
        scan_tasks = _g.get("scan_tasks")
    if scan_features is None:
        scan_features = _g.get("scan_features")
    if scan_signals is None:
        scan_signals = _g.get("scan_signals")
    if list_tmux_panes is None:
        list_tmux_panes = _g.get("list_tmux_panes")

    # discover_subprojects: 모듈 레벨 (테스트 패치 반영)
    _discover_subprojects = _g.get("discover_subprojects")
    _dedup_fn = _g.get("_dedup_workitems_by_id")
    _agg_scan = _g.get("_aggregated_scan")

    try:
        # --- 1. Query parameter parsing ---
        raw_path = getattr(handler, "path", "") or ""
        _qs = urlsplit(raw_path).query
        qp = _core._parse_state_query_params(_qs)
        subproject: str = qp["subproject"]
        include_pool: bool = qp["include_pool"]

        project_root: str = _core._server_attr(handler, "project_root")
        docs_dir: str = _core._server_attr(handler, "docs_dir")

        # --- 2. Subproject discovery ---
        available_subprojects: List[str] = _discover_subprojects(docs_dir)
        is_multi_mode: bool = bool(available_subprojects)

        # --- 3. effective_docs_dir ---
        effective_docs_dir: str = _core._resolve_effective_docs_dir(docs_dir, subproject)

        # --- 3b. features aggregator ---
        _base_docs = docs_dir
        _avail_sps = available_subprojects
        _project_root_path = Path(project_root) if project_root else None

        def _scan_features_api(docs_dir_arg) -> List["WorkItem"]:
            if subproject == "all" and is_multi_mode:
                items: List["WorkItem"] = list(
                    _agg_scan(Path(_base_docs), _project_root_path, scan_features) or []
                )
                for sp in _avail_sps:
                    items.extend(
                        _agg_scan(Path(_base_docs) / sp, _project_root_path, scan_features) or []
                    )
                return _dedup_fn(items)
            if subproject and subproject != "all" and is_multi_mode:
                items = list(
                    _agg_scan(Path(_base_docs), _project_root_path, scan_features) or []
                )
                items.extend(
                    _agg_scan(Path(docs_dir_arg), _project_root_path, scan_features) or []
                )
                return _dedup_fn(items)
            return _agg_scan(Path(docs_dir_arg), _project_root_path, scan_features)

        def _scan_tasks_api(docs_dir_arg) -> List["WorkItem"]:
            return _agg_scan(Path(docs_dir_arg), _project_root_path, scan_tasks)

        # --- 4. Build base snapshot ---
        payload = _core._build_state_snapshot(
            project_root=project_root,
            docs_dir=effective_docs_dir,
            scan_tasks=_scan_tasks_api,
            scan_features=_scan_features_api,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )

        # --- 5. Post-processing pipeline ---
        payload = _core._apply_subproject_filter(payload, subproject)
        payload = _core._apply_include_pool(payload, include_pool)

        # --- 6. Inject top-level fields ---
        project_name: str = (
            getattr(getattr(handler, "server", None), "project_name", None)
            or os.path.basename(project_root)
            or ""
        )
        _wbs_tasks: List["WorkItem"] = payload.get("wbs_tasks") or []
        distinct_domains: List[str] = sorted({
            getattr(t, "domain", None) or ""
            for t in _wbs_tasks
            if getattr(t, "domain", None)
        })
        payload = {
            **payload,
            "subproject": subproject,
            "available_subprojects": available_subprojects,
            "is_multi_mode": is_multi_mode,
            "project_name": project_name,
            "distinct_domains": distinct_domains,
        }

    except Exception as exc:
        sys.stderr.write(f"/api/state build failed: {exc!r}\n")
        _core._json_error(handler, 500, f"internal error: {exc!r}")
        return

    _core._json_response(handler, 200, payload)
