"""monitor_server.api — /api/* 엔드포인트 핸들러 (TSK-02-02).

4개 public 함수:
  handle_state(handler, params, model)
  handle_graph(handler, params, model)
  handle_task_detail(handler, params, model)
  handle_merge_status(handler, params, model)

시그니처: def handle_X(handler, params: dict, model) -> None
  - handler: BaseHTTPRequestHandler 인스턴스
  - params: 쿼리 파라미터 dict (parse_qs 결과, 이미 파싱된 값)
  - model: 대시보드 모델 (현재 handle_graph/handle_state에서만 사용; 미래 확장용)

설계 결정:
  - 공용 유틸(_json_response, _json_error, _server_attr, _now_iso_z 등)은
    monitor-server.py를 역방향 import하지 않고 이 모듈에 직접 정의한다.
    (순환참조 방지: monitor-server.py → monitor_server.api 방향만 허용)
  - scan_* 함수들은 handle_graph/handle_state의 기본값 파라미터로 주입한다.
  - monitor-server.py의 기존 _handle_api_* 함수들은 shim으로 남겨
    기존 테스트 호환을 유지한다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional


# ---------------------------------------------------------------------------
# 공용 유틸 (monitor-server.py에도 동일 함수 존재 — 순환참조 방지 복제)
# ---------------------------------------------------------------------------

def _now_iso_z() -> str:
    """Return current UTC time as ISO-8601 string with 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_response(handler, status: int, payload) -> None:
    """Write *payload* as JSON to *handler* with the mandated headers.

    Headers: Content-Type, Content-Length, Cache-Control: no-store.
    """
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _json_error(handler, status: int, message: str) -> None:
    """Send a standard JSON error envelope: {"error": <msg>, "code": <status>}."""
    _json_response(handler, status, {"error": message, "code": status})


def _server_attr(handler, name: str, default: str = "") -> str:
    """Read handler.server.<name> defensively, returning a string."""
    server = getattr(handler, "server", None)
    value = getattr(server, name, default) or default
    return str(value)


def _resolve_effective_docs_dir(docs_dir: str, subproject: str) -> str:
    """Resolve effective docs directory for a given subproject.

    ``subproject == "all"`` or empty/None → docs_dir unchanged.
    Otherwise returns os.path.join(docs_dir, subproject).
    """
    if not subproject or subproject == "all":
        return docs_dir
    return os.path.join(docs_dir, subproject)


def _discover_subprojects(docs_dir) -> List[str]:
    """Return sorted list of subproject directory names under docs_dir.

    A child directory qualifies as a subproject iff it contains a wbs.md file.
    Returns [] when docs_dir does not exist or is not a directory.
    """
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        return []
    return [
        child.name
        for child in sorted(docs_dir.iterdir())
        if child.is_dir() and (child / "wbs.md").is_file()
    ]


# ---------------------------------------------------------------------------
# Constants (api-local)
# ---------------------------------------------------------------------------

_API_GRAPH_PATH = "/api/graph"
_API_STATE_PATH = "/api/state"
_API_TASK_DETAIL_PATH = "/api/task-detail"
_API_MERGE_STATUS_PATH = "/api/merge-status"

_DEP_ANALYSIS_TIMEOUT = 3  # seconds
_RUNNING_STATUSES = {"[dd]", "[im]", "[ts]"}
_GRAPH_PHASE_TAIL_LIMIT = 3

_WBS_SECTION_RE = re.compile(r"^### (?P<id>TSK-\S+):", re.MULTILINE)
_TSK_ID_VALID_RE = re.compile(r"^TSK-\S+$")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

_MERGE_STATUS_FILENAME = "merge-status.json"
_MERGE_STALE_SECONDS = 1800

LOG_NAMES = ("build-report.md", "test-report.md")
_MAX_LOG_TAIL_LINES = 200


# ---------------------------------------------------------------------------
# /api/graph helpers
# ---------------------------------------------------------------------------

def _task_attr(task, name: str, default=None):
    """Read *name* from a task that may be a dict or an object."""
    return task.get(name, default) if isinstance(task, dict) else getattr(task, name, default)


def _task_id(task) -> str:
    """Return the canonical task ID string regardless of dict/object form."""
    return _task_attr(task, "id", "")


def _task_depends(task) -> list:
    """Return the dependency list for a task, always as a list."""
    return _task_attr(task, "depends", None) or []


def _sig_attr(sig, name: str) -> str:
    """Read *name* from a signal dict or object."""
    return sig.get(name, "") if isinstance(sig, dict) else getattr(sig, name, "")


def _serialize_phase_history_tail_for_graph(
    entries,
    limit: int = _GRAPH_PHASE_TAIL_LIMIT,
) -> List[dict]:
    """Convert last *limit* PhaseEntry items to /api/graph spec dicts."""
    if not entries:
        return []
    tail = entries[-limit:] if limit > 0 else []
    return [
        {
            "event": entry.event,
            "from": entry.from_status,
            "to": entry.to_status,
            "at": entry.at,
            "elapsed_seconds": entry.elapsed_seconds,
        }
        for entry in tail
    ]


def _signal_set(signals: Optional[Iterable], kind: str) -> set:
    """Return set of task_ids whose signal kind matches *kind*."""
    if not signals:
        return set()
    return {
        _sig_attr(sig, "task_id")
        for sig in signals
        if _sig_attr(sig, "kind") == kind
    }


def _derive_node_status(task, signals) -> str:
    """Derive display status for a graph node.

    Priority: bypassed > failed > done > running > pending.
    """
    tid = _task_id(task)
    task_signals = {
        _sig_attr(sig, "kind")
        for sig in signals
        if _sig_attr(sig, "task_id") == tid
    }

    if _task_attr(task, "bypassed", False):
        return "bypassed"

    has_failed_signal = "failed" in task_signals
    last_ev = _task_attr(task, "last_event", "") or ""
    if has_failed_signal or last_ev.endswith(".fail") or last_ev == "fail":
        return "failed"

    status = _task_attr(task, "status", "") or ""
    if status == "[xx]":
        return "done"

    if "running" in task_signals or status in _RUNNING_STATUSES:
        return "running"

    return "pending"


def _build_graph_payload(tasks, signals, graph_stats: dict, docs_dir_str: str, subproject: str) -> dict:
    """Assemble the /api/graph response payload."""
    fan_in_map: dict = graph_stats.get("fan_in_map", {})
    fan_out_map: dict = graph_stats.get("fan_out_map", {})
    critical_path: dict = graph_stats.get("critical_path", {"nodes": [], "edges": []})
    bottleneck_ids: list = graph_stats.get("bottleneck_ids", [])
    bottleneck_set: set = set(bottleneck_ids)
    cp_node_set = set(critical_path.get("nodes", []))

    status_counts = {"done": 0, "running": 0, "pending": 0, "failed": 0, "bypassed": 0}
    nodes = []

    task_id_set = {_task_id(t) for t in tasks}
    running_ids_set = _signal_set(signals, "running")

    for task in tasks:
        node_status = _derive_node_status(task, signals)
        status_counts[node_status] += 1

        tid = _task_id(task)
        ph_tail = _task_attr(task, "phase_history_tail") or []
        nodes.append({
            "id": tid,
            "label": _task_attr(task, "title") or tid,
            "status": node_status,
            "is_critical": tid in cp_node_set,
            "is_bottleneck": tid in bottleneck_set,
            "fan_in": fan_in_map.get(tid, 0),
            "fan_out": fan_out_map.get(tid, 0),
            "bypassed": _task_attr(task, "bypassed", False),
            "wp_id": _task_attr(task, "wp_id") or "",
            "depends": list(_task_depends(task)),
            "phase_history_tail": _serialize_phase_history_tail_for_graph(ph_tail),
            "last_event": _task_attr(task, "last_event"),
            "last_event_at": _task_attr(task, "last_event_at"),
            "elapsed_seconds": _task_attr(task, "elapsed_seconds"),
            "is_running_signal": tid in running_ids_set,
            "domain": _task_attr(task, "domain") or "-",
            "model": _task_attr(task, "model") or "-",
        })

    edges = []
    for task in tasks:
        tid = _task_id(task)
        for dep_id in _task_depends(task):
            if dep_id in task_id_set:
                edges.append({"source": dep_id, "target": tid})

    total = len(nodes)
    stats = {
        "total": total,
        "done": status_counts["done"],
        "running": status_counts["running"],
        "pending": status_counts["pending"],
        "failed": status_counts["failed"],
        "bypassed": status_counts["bypassed"],
        "max_chain_depth": graph_stats.get("max_chain_depth", 0),
        "critical_path_length": len(critical_path.get("nodes", [])),
        "bottleneck_count": len(bottleneck_ids),
    }

    return {
        "subproject": subproject,
        "docs_dir": docs_dir_str,
        "generated_at": _now_iso_z(),
        "stats": stats,
        "critical_path": critical_path,
        "nodes": nodes,
        "edges": edges,
    }


def _build_fan_in_map(tasks) -> dict:
    """Compute fan-in counts for each task from its dependents.

    Used by monitor-server.py as a graph-stats fallback (not called within
    api.py itself).
    """
    fan_in_map = {_task_id(t): 0 for t in tasks}
    for t in tasks:
        for dep_id in _task_depends(t):
            if dep_id in fan_in_map:
                fan_in_map[dep_id] += 1
    return fan_in_map


def _call_dep_analysis_graph_stats(tasks_input: list, dep_analysis_script: str):
    """Run dep-analysis.py --graph-stats. Returns (dict, "") or (None, error_msg)."""
    try:
        proc = subprocess.run(
            [sys.executable, dep_analysis_script, "--graph-stats"],
            input=json.dumps(tasks_input, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=_DEP_ANALYSIS_TIMEOUT,
            check=False,
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as exc:
        return None, f"dep-analysis error: {exc!r}"

    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or "").strip()[:200]
        return None, f"dep-analysis exited {proc.returncode}: {stderr_snippet}"

    try:
        return json.loads(proc.stdout), ""
    except (ValueError, TypeError) as exc:
        return None, f"dep-analysis bad JSON: {exc!r}"


# ---------------------------------------------------------------------------
# /api/task-detail helpers
# ---------------------------------------------------------------------------

def _extract_wbs_section(wbs_md: str, task_id: str) -> str:
    """Extract WBS section for task_id from wbs_md. Returns stripped text or ''."""
    matches = list(_WBS_SECTION_RE.finditer(wbs_md))
    for i, m in enumerate(matches):
        if m.group("id") != task_id:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wbs_md)
        h2_match = re.search(r"^## ", wbs_md[start:end], re.MULTILINE)
        if h2_match:
            end = start + h2_match.start()
        return wbs_md[start:end].strip()
    return ""


def _tail_report(path, max_lines: int = _MAX_LOG_TAIL_LINES) -> dict:
    """Return tail dict for a single log file.

    Schema: {name, tail, truncated, lines_total, exists}.
    """
    name = Path(path).name
    if not Path(path).exists():
        return {"name": name, "tail": "", "truncated": False, "lines_total": 0, "exists": False}
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"name": name, "tail": "", "truncated": False, "lines_total": 0, "exists": False}
    raw = _ANSI_RE.sub("", raw)
    all_lines = raw.splitlines()
    lines_total = len(all_lines)
    truncated = lines_total > max_lines
    tail_lines = all_lines[-max_lines:] if truncated else all_lines
    return {
        "name": name,
        "tail": "\n".join(tail_lines),
        "truncated": truncated,
        "lines_total": lines_total,
        "exists": True,
    }


def _collect_logs(task_dir) -> list:
    """Return [{name, tail, truncated, lines_total, exists}] for LOG_NAMES."""
    return [_tail_report(Path(task_dir) / name) for name in LOG_NAMES]


def _collect_artifacts(task_dir) -> list:
    """Return [{name, path, exists, size}] for design/test-report/refactor."""
    artifact_names = ("design.md", "test-report.md", "refactor.md")
    result = []
    for name in artifact_names:
        filepath = Path(task_dir) / name
        try:
            st = filepath.stat()
            exists = True
            size = st.st_size
        except OSError:
            exists = False
            size = 0
        raw = str(Path(task_dir) / name)
        docs_idx = raw.find("docs/")
        rel = raw[docs_idx:] if docs_idx >= 0 else raw
        result.append({"name": name, "path": rel, "exists": exists, "size": size})
    return result


def _extract_title_from_section(section_md: str) -> str:
    """Extract task title from the first line of a WBS section."""
    first_line = section_md.splitlines()[0] if section_md else ""
    tsk_pos = first_line.find("TSK-")
    if tsk_pos < 0:
        return ""
    colon_pos = first_line.find(":", tsk_pos)
    if colon_pos < 0:
        return ""
    return first_line[colon_pos + 1:].strip()


def _extract_wp_id(section_md: str, wbs_md: str, task_id: str) -> str:
    """Resolve wp_id for a task."""
    for line in section_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("- wp:"):
            return stripped[len("- wp:"):].strip()
    section_start = wbs_md.find(f"### {task_id}:")
    if section_start > 0:
        preceding = wbs_md[:section_start]
        wp_match = None
        for m in re.finditer(r"^## (WP-\S+)", preceding, re.MULTILINE):
            wp_match = m
        if wp_match:
            return wp_match.group(1).rstrip(":")
    return ""


def _load_state_json(task_dir) -> dict:
    """Load state.json from task_dir. Returns {"status": "[ ]"} on missing/corrupt."""
    state_json_path = Path(task_dir) / "state.json"
    if not state_json_path.exists():
        return {"status": "[ ]"}
    try:
        with open(state_json_path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        return {"status": "[ ]"}


def _build_task_detail_payload(task_id: str, subproject: str, effective_docs_dir, wbs_md: str):
    """Build /api/task-detail payload. Returns (status_code, dict)."""
    if not _TSK_ID_VALID_RE.match(task_id):
        return (400, {"error": f"Invalid task_id format: {task_id!r}", "code": 400})
    wbs_section_md = _extract_wbs_section(wbs_md, task_id)
    if not wbs_section_md:
        return (404, {"error": f"Task {task_id!r} not found in wbs.md", "code": 404})
    title = _extract_title_from_section(wbs_section_md)
    wp_id = _extract_wp_id(wbs_section_md, wbs_md, task_id)
    task_dir = Path(effective_docs_dir) / "tasks" / task_id
    state = _load_state_json(task_dir)
    artifacts = _collect_artifacts(task_dir)
    logs = _collect_logs(task_dir)
    return (200, {
        "task_id": task_id, "title": title, "wp_id": wp_id, "source": "wbs",
        "wbs_section_md": wbs_section_md, "state": state, "artifacts": artifacts,
        "logs": logs,
    })


# ---------------------------------------------------------------------------
# /api/merge-status helpers
# ---------------------------------------------------------------------------

def _badge_label_for_state(state: str) -> str:
    """Return a human-readable badge label for a merge state.

    Called by monitor-server.py via the shim/flat-module pattern.
    """
    return {
        "ready": "\U0001f7e2 머지 가능",
        "waiting": "\U0001f7e1 대기 중",
        "conflict": "\U0001f534 충돌",
    }.get(state, "⚫ 알 수 없음")


def _load_merge_status_file(path: Path) -> Optional[dict]:
    """Load and return a merge-status.json file. Returns None on error."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None


def _is_merge_status_stale(path: Path, data: dict) -> bool:
    """Compute is_stale from file mtime. Falls back to data field on OSError."""
    try:
        return (time.time() - path.stat().st_mtime) > _MERGE_STALE_SECONDS
    except OSError:
        return data.get("is_stale", False)


def _load_merge_status(docs_dir: str, wp_id: Optional[str]):
    """Load merge-status.json for a single WP or all WPs.

    Returns (payload, status_code).
    - wp_id=None: returns list of summary dicts
    - wp_id specified: returns full dict or ({}, 404) if missing
    """
    wp_state_dir = Path(docs_dir) / "wp-state"

    if wp_id:
        status_file = wp_state_dir / wp_id / _MERGE_STATUS_FILENAME
        if not status_file.exists():
            return ({}, 404)
        data = _load_merge_status_file(status_file)
        if data is None:
            return ({}, 404)
        data["is_stale"] = _is_merge_status_stale(status_file, data)
        return (data, 200)
    else:
        summary = []
        if not wp_state_dir.exists():
            return (summary, 200)
        try:
            entries = list(wp_state_dir.iterdir())
        except OSError:
            return (summary, 200)
        for entry in sorted(entries):
            if not entry.is_dir():
                continue
            status_file = entry / _MERGE_STATUS_FILENAME
            if not status_file.exists():
                continue
            data = _load_merge_status_file(status_file)
            if data is None:
                continue
            row = {
                "wp_id": data.get("wp_id", entry.name),
                "state": data.get("state", "unknown"),
                "pending_count": data.get("pending_count", 0),
                "conflict_count": data.get("conflict_count", 0),
                "is_stale": _is_merge_status_stale(status_file, data),
            }
            summary.append(row)
        return (summary, 200)


# ---------------------------------------------------------------------------
# Public handle_* functions (TSK-02-02 contract)
# ---------------------------------------------------------------------------

def _delegate(handler, fn_name: str, **kwargs) -> None:
    """Resolve *fn_name* from the flat module and call it with handler + kwargs.

    Sends a 500 JSON error when the function cannot be found, so callers need
    no boilerplate None-check.
    """
    _impl = _get_monitor_server_fn(fn_name)
    if _impl is None:
        _json_error(handler, 500, f"{fn_name} not available")
        return
    _impl(handler, **kwargs)


def handle_state(
    handler,
    params: dict,
    model,
    *,
    scan_tasks=None,
    scan_features=None,
    scan_signals=None,
    list_tmux_panes=None,
) -> None:
    """Handle GET /api/state. Delegates to monitor-server.py's _handle_api_state.

    Resolves the implementation lazily from the loaded monitor_server flat
    module (monitor-server.py loaded as 'monitor_server' by test loaders) or
    via a late import to avoid circular references.

    params: pre-parsed query dict (not used directly — handler.path is re-parsed
            for full compatibility with the existing implementation).
    """
    extra = {
        k: v for k, v in {
            "scan_tasks": scan_tasks,
            "scan_features": scan_features,
            "scan_signals": scan_signals,
            "list_tmux_panes": list_tmux_panes,
        }.items() if v is not None
    }
    _delegate(handler, "_handle_api_state", **extra)


def handle_graph(
    handler,
    params: dict,
    model,
    *,
    scan_tasks_fn=None,
    scan_signals_fn=None,
) -> None:
    """Handle GET /api/graph."""
    extra = {
        k: v for k, v in {
            "scan_tasks_fn": scan_tasks_fn,
            "scan_signals_fn": scan_signals_fn,
        }.items() if v is not None
    }
    _delegate(handler, "_handle_graph_api", **extra)


def handle_task_detail(handler, params: dict, model) -> None:
    """Handle GET /api/task-detail."""
    _delegate(handler, "_handle_api_task_detail")


def handle_merge_status(handler, params: dict, model) -> None:
    """Handle GET /api/merge-status."""
    _delegate(handler, "_handle_api_merge_status")


# ---------------------------------------------------------------------------
# Internal: late-binding to monitor-server.py functions
# ---------------------------------------------------------------------------

def _get_monitor_server_fn(name: str):
    """Return a function from the loaded monitor_server flat module.

    Test loaders register monitor-server.py under 'monitor_server' key in
    sys.modules. In production, monitor-server.py loads this package and
    the flat module is already in sys.modules['monitor_server'] — BUT since
    the flat module IS monitor-server.py itself and it imports this package,
    after this package is loaded the flat module is already set.

    Fallback: if 'monitor_server' in sys.modules has __path__ (i.e. is the
    package, not the flat file), try to import the flat file from scripts/.
    """
    mod = sys.modules.get("monitor_server")
    if mod is not None and not hasattr(mod, "__path__"):
        # flat module (monitor-server.py loaded as monitor_server)
        fn = getattr(mod, name, None)
        if fn is not None:
            return fn

    # Try loading the flat file from the scripts/ directory
    scripts_dir = Path(__file__).resolve().parent.parent
    flat_path = scripts_dir / "monitor-server.py"
    if not flat_path.exists():
        return None

    import importlib.util as _ilu  # local import: only on fallback path
    _spec = _ilu.spec_from_file_location("_monitor_server_flat", flat_path)
    if _spec is None:
        return None
    try:
        _flat = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_flat)
        return getattr(_flat, name, None)
    except Exception:
        return None
