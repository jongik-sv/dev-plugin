"""monitor_server.handlers_graph — /api/graph and /api/task-detail HTTP handlers.

[core-http-split:C1-2]

Migrated from core.py:
  _handle_graph_api          (was L5023–L5168)
  _handle_api_task_detail    (was L5339–L5362)

순환 참조 회피: core.py를 직접 import하지 않는다.
  - caches, api, workitems, signals 는 모듈 레벨 직접 import (순환 없음).
  - core 경유 심볼(_server_attr, _resolve_effective_docs_dir, _aggregated_scan,
    _call_dep_analysis_graph_stats, _json_response, _json_error, _graph_etag,
    _get_if_none_match)은 함수 내부에서 지연 import.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    from monitor_server.signals import SignalEntry
    from monitor_server.workitems import WorkItem

# ---------------------------------------------------------------------------
# Constants (local copies — mirrors core.py values)
# ---------------------------------------------------------------------------

_API_GRAPH_PATH = "/api/graph"
_DEP_ANALYSIS_TIMEOUT = 3  # seconds
_RUNNING_STATUSES = {"[dd]", "[im]", "[ts]"}
_GRAPH_PHASE_TAIL_LIMIT = 3

_API_MERGE_STATUS_PATH = "/api/merge-status"
_MERGE_STATUS_FILENAME = "merge-status.json"
_MERGE_STALE_SECONDS = 1800


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def _handle_graph_api(
    handler,
    *,
    scan_tasks_fn: "Optional[Callable[[Any], List[WorkItem]]]" = None,
    scan_signals_fn: "Optional[Callable[[], List[SignalEntry]]]" = None,
) -> None:
    """Handle ``GET /api/graph`` on *handler*.

    Migrated from core.py _handle_graph_api.
    순환 참조 회피: core 심볼은 함수 내부에서 지연 import.
    """
    from monitor_server import core as _core  # noqa: PLC0415
    from monitor_server.caches import _GRAPH_CACHE  # noqa: PLC0415

    if scan_tasks_fn is None:
        scan_tasks_fn = _core.scan_tasks
    if scan_signals_fn is None:
        scan_signals_fn = _core.scan_signals_cached

    # Parse subproject query param
    parsed = urlsplit(handler.path)
    qs = parse_qs(parsed.query)
    subproject = (qs.get("subproject") or ["all"])[0] or "all"

    # Resolve effective_docs_dir
    base_docs_dir = _core._server_attr(handler, "docs_dir")
    if subproject == "all":
        effective_docs_dir = base_docs_dir
    else:
        effective_docs_dir = str(Path(base_docs_dir) / subproject)

    # --- Cache check ---
    _cache_key = f"{base_docs_dir}::{subproject}"
    cached_entry, cache_hit = _GRAPH_CACHE.get(_cache_key)
    if cache_hit and cached_entry is not None:
        cached_payload = cached_entry.get("payload")
        cached_etag = cached_entry.get("etag", "")
        if_none_match = _core._get_if_none_match(handler)
        if cached_etag and if_none_match and cached_etag == if_none_match:
            handler.send_response(304)
            handler.send_header("ETag", cached_etag)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            return
        try:
            json_bytes = json.dumps(cached_payload, default=str, ensure_ascii=False).encode("utf-8")
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(json_bytes)))
            handler.send_header("Cache-Control", "no-store")
            if cached_etag:
                handler.send_header("ETag", cached_etag)
            handler.end_headers()
            handler.wfile.write(json_bytes)
            return
        except Exception:
            pass  # fall through to fresh compute

    # --- Cache miss: full compute path ---
    project_root_str = _core._server_attr(handler, "project_root")
    project_root_path = Path(project_root_str) if project_root_str else None
    try:
        tasks = list(
            _core._aggregated_scan(
                Path(effective_docs_dir), project_root_path, scan_tasks_fn,
            ) or []
        )
        signals = list(scan_signals_fn() or [])
    except Exception as exc:
        sys.stderr.write(f"/api/graph scan failed: {exc!r}\n")
        _core._json_error(handler, 500, f"scan error: {exc!r}")
        return

    tasks_input = [
        {
            "tsk_id": t.id,
            "depends": ", ".join(t.depends) if t.depends else "-",
            "status": t.status or "[ ]",
            "bypassed": t.bypassed,
            "title": t.title or "",
            "wp_id": t.wp_id or "",
        }
        for t in tasks
    ]

    graph_stats, err = _core._call_dep_analysis_graph_stats(tasks_input)
    if graph_stats is None:
        sys.stderr.write(f"/api/graph dep-analysis failed: {err}\n")
        _core._json_error(handler, 500, err)
        return

    # Inject locally-computed fan_in_map
    from monitor_server import api as _api  # noqa: PLC0415
    graph_stats.setdefault("fan_in_map", _api._build_fan_in_map(tasks))

    try:
        payload = _api._build_graph_payload(tasks, signals, graph_stats, effective_docs_dir, subproject)
    except Exception as exc:
        sys.stderr.write(f"/api/graph build payload failed: {exc!r}\n")
        _core._json_error(handler, 500, f"payload build error: {exc!r}")
        return

    try:
        json_bytes = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
        _etag_payload = {k: v for k, v in payload.items() if k != "generated_at"}
        _etag_bytes = json.dumps(_etag_payload, default=str, ensure_ascii=False, sort_keys=True).encode("utf-8")
        etag = _core._graph_etag(_etag_bytes)
    except Exception:
        json_bytes = None  # type: ignore[assignment]
        etag = ""

    _GRAPH_CACHE.set(_cache_key, {"payload": payload, "etag": etag})

    if json_bytes is None:
        _core._json_response(handler, 200, payload)
        return

    if etag:
        inm = _core._get_if_none_match(handler)
        if inm and inm.strip() == etag:
            handler.send_response(304)
            handler.send_header("ETag", etag)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            return

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(json_bytes)))
    handler.send_header("Cache-Control", "no-store")
    if etag:
        handler.send_header("ETag", etag)
    handler.end_headers()
    handler.wfile.write(json_bytes)


def _handle_api_task_detail(handler) -> None:
    """Handle GET /api/task-detail.

    Migrated from core.py _handle_api_task_detail.
    순환 참조 회피: core 심볼은 함수 내부에서 지연 import.
    """
    from monitor_server import core as _core  # noqa: PLC0415
    from monitor_server import api as _api  # noqa: PLC0415
    from monitor_server.workitems import discover_subprojects  # noqa: PLC0415

    try:
        raw_path = getattr(handler, "path", "") or ""
        qs = urlsplit(raw_path).query
        qp = parse_qs(qs, keep_blank_values=False)
        task_id = (qp.get("task") or [""])[0] or ""
        raw_sp = (qp.get("subproject") or ["all"])[0] or "all"
        base_docs_dir = _core._server_attr(handler, "docs_dir")
        available_subprojects = discover_subprojects(base_docs_dir)
        if raw_sp != "all" and raw_sp not in available_subprojects:
            raw_sp = "all"
        effective_docs_dir = _core._resolve_effective_docs_dir(base_docs_dir, raw_sp)
        wbs_path = Path(effective_docs_dir) / "wbs.md"
        try:
            with open(wbs_path, "r", encoding="utf-8") as fp:
                wbs_md = fp.read()
        except OSError:
            wbs_md = ""
        status, payload = _api._build_task_detail_payload(task_id, raw_sp, effective_docs_dir, wbs_md)
        _core._json_response(handler, status, payload)
    except Exception as exc:
        sys.stderr.write(f"/api/task-detail error: {exc!r}\n")
        _core._json_error(handler, 500, str(exc))
