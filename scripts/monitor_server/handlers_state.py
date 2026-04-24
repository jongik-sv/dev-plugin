"""monitor_server.handlers_state — /api/state HTTP handler.

[core-http-split:C1-3]

Migrated from core.py:
  _handle_api_state  (was L6362–L6484)

순환 참조 회피: core.py를 직접 import하지 않는다.
  - workitems, signals, panes 는 모듈 레벨 직접 import (순환 없음).
  - core 경유 심볼(_parse_state_query_params, _server_attr,
    _resolve_effective_docs_dir, _aggregated_scan, _dedup_workitems_by_id,
    _build_state_snapshot, _apply_subproject_filter, _apply_include_pool,
    _json_response, _json_error)은 함수 내부에서 지연 import.
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
    순환 참조 회피: core 심볼은 함수 내부에서 지연 import.
    """
    from monitor_server import core as _core  # noqa: PLC0415
    from monitor_server.workitems import (  # noqa: PLC0415
        scan_tasks as _scan_tasks_default,
        scan_features as _scan_features_default,
        discover_subprojects,
        _dedup_workitems_by_id,
        _aggregated_scan,
    )
    from monitor_server.signals import scan_signals as _scan_signals_default  # noqa: PLC0415
    from monitor_server.panes import list_tmux_panes as _list_tmux_panes_default  # noqa: PLC0415

    if scan_tasks is None:
        scan_tasks = _scan_tasks_default
    if scan_features is None:
        scan_features = _scan_features_default
    if scan_signals is None:
        scan_signals = _scan_signals_default
    if list_tmux_panes is None:
        list_tmux_panes = _list_tmux_panes_default

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
        available_subprojects: List[str] = discover_subprojects(docs_dir)
        is_multi_mode: bool = bool(available_subprojects)

        # --- 3. effective_docs_dir for scan_tasks / scan_features ---
        effective_docs_dir: str = _core._resolve_effective_docs_dir(docs_dir, subproject)

        # --- 3b. features aggregator for "all" in multi-mode ---
        _base_docs = docs_dir
        _avail_sps = available_subprojects
        _project_root_path = Path(project_root) if project_root else None

        def _scan_features_api(docs_dir_arg) -> List["WorkItem"]:
            if subproject == "all" and is_multi_mode:
                items: List["WorkItem"] = list(
                    _aggregated_scan(Path(_base_docs), _project_root_path, scan_features) or []
                )
                for sp in _avail_sps:
                    items.extend(
                        _aggregated_scan(Path(_base_docs) / sp, _project_root_path, scan_features) or []
                    )
                return _dedup_workitems_by_id(items)
            if subproject and subproject != "all" and is_multi_mode:
                items = list(
                    _aggregated_scan(Path(_base_docs), _project_root_path, scan_features) or []
                )
                items.extend(
                    _aggregated_scan(Path(docs_dir_arg), _project_root_path, scan_features) or []
                )
                return _dedup_workitems_by_id(items)
            return _aggregated_scan(Path(docs_dir_arg), _project_root_path, scan_features)

        def _scan_tasks_api(docs_dir_arg) -> List["WorkItem"]:
            return _aggregated_scan(Path(docs_dir_arg), _project_root_path, scan_tasks)

        # --- 4. Build base snapshot using effective_docs_dir ---
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
