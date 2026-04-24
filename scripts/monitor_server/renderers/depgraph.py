"""monitor_server.renderers.depgraph — 의존성 그래프 섹션 SSR 렌더러.

TSK-02-01 커밋 5: _section_dep_graph + _build_graph_payload 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List

try:
    from ._util import (
        _t,
        _signal_set,
        _derive_node_status,
        _serialize_phase_history_tail_for_graph,
        _now_iso_z,
    )
    from .taskrow import _phase_data_attr  # noqa: F401 — re-exports via monitor_server.renderers.depgraph for downstream consumers
except ImportError:
    # Standalone load (e.g. importlib.util.spec_from_file_location in unit tests
    # that only exercise pure helpers like render_legend()). _util/taskrow helpers
    # stay unbound; any caller needing them (e.g. _section_dep_graph) will fail
    # loudly, which is the right behavior.
    pass


def render_legend(wheel_label: str = "") -> str:
    """Render the dep-graph legend HTML.

    TSK-03-03 (FR-05): Critical Path 항목을 Failed 와 별도 <li>로 분리.
    구조는 <ul id="dep-graph-legend"> + <li class="legend-{state} leg-item">.
    크리티컬 swatch 색은 #f59e0b (앰버, --critical 토큰과 동일 hex).

    Args:
        wheel_label: wheel-zoom 토글 라벨 텍스트 (이미 HTML-escape 되어 있다고 가정).
    """
    return (
        '<ul id="dep-graph-legend" class="dep-graph-legend">'
        '<li class="legend-done leg-item" style="color:#22c55e">&#9632; done</li>'
        '<li class="legend-running leg-item" style="color:#eab308">&#9632; running</li>'
        '<li class="legend-pending leg-item" style="color:#94a3b8">&#9632; pending</li>'
        '<li class="legend-failed leg-item" style="color:#ef4444">&#9632; failed</li>'
        '<li class="legend-bypassed leg-item" style="color:#a855f7">&#9632; bypassed</li>'
        '<li class="legend-critical leg-item" style="color:#f59e0b">&#9632; critical path</li>'
        '<label class="dep-graph-wheel" for="dep-graph-wheel-toggle">'
        '<input type="checkbox" id="dep-graph-wheel-toggle">'
        f'<span>{wheel_label}</span></label>'
        '</ul>'
    )


def _section_dep_graph(lang: str = "ko", subproject: str = "all") -> str:
    """Render the Dependency Graph section SSR skeleton (TRD §3.9.5).

    Returns a ``<section id="dep-graph">`` block containing:
    - ``.section-head`` with i18n h2 + ``<aside id="dep-graph-summary">``
    - ``.dep-graph-wrap``: canvas div (height 520px) + legend div
    - 4 vendor ``<script>`` tags in load order:
      dagre → cytoscape → cytoscape-dagre → graph-client

    The ``subproject`` value is HTML-escaped and injected as
    ``data-subproject="..."`` on the root ``<section>`` element so that
    graph-client.js can read it without inline scripts.
    """
    sp_esc = html.escape(subproject or "all", quote=True)
    heading = _t(lang, "dep_graph")

    # TSK-04-04: SSR chip markup with i18n labels.
    # graph-client.js:updateSummary uses [data-stat] selector — tag change
    # (<span>→<b>) is intentional and selector-compatible.
    _STAT_STATES = ("total", "done", "running", "pending", "failed", "bypassed")
    chips = " ".join(
        f'<span class="dep-stat dep-stat-{s}">'
        f'<em>{html.escape(_t(lang, f"dep_stat_{s}"))}</em>'
        f' <b data-stat="{s}">-</b></span>'
        for s in _STAT_STATES
    )
    summary_html = f'<aside id="dep-graph-summary" class="dep-graph-summary">{chips}</aside>'

    wheel_label = html.escape(_t(lang, "dep_wheel_zoom"))
    legend_html = render_legend(wheel_label=wheel_label)

    # graph-client.js는 개발 중 자주 바뀌므로 mtime 기반 cache-buster를 붙여 브라우저 캐시를 무효화한다.
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[3])
    gc_path = Path(plugin_root) / "skills" / "dev-monitor" / "vendor" / "graph-client.js"
    try:
        gc_ver = str(int(gc_path.stat().st_mtime))
    except OSError:
        gc_ver = "0"

    scripts_html = (
        '<script src="/static/dagre.min.js"></script>\n'
        '<script src="/static/cytoscape.min.js"></script>\n'
        '<script src="/static/cytoscape-node-html-label.min.js"></script>\n'
        '<script src="/static/cytoscape-dagre.min.js"></script>\n'
        f'<script src="/static/graph-client.js?v={gc_ver}"></script>'
    )

    return (
        f'<section id="dep-graph" data-section="dep-graph"'
        f' data-subproject="{sp_esc}">\n'
        '  <div class="section-head">\n'
        f'    <div><h2>{html.escape(heading)}</h2></div>\n'
        f'    {summary_html}\n'
        '  </div>\n'
        '  <div class="dep-graph-wrap">\n'
        '    <div id="dep-graph-canvas" style="min-height:640px; height:clamp(640px, 78vh, 1400px);"></div>\n'
        f'    {legend_html}\n'
        '  </div>\n'
        f'{scripts_html}\n'
        '</section>'
    )


def _build_graph_payload(
    tasks: "List",
    signals: "List",
    graph_stats: dict,
    docs_dir_str: str,
    subproject: str,
) -> dict:
    """Assemble the /api/graph response payload.

    Args:
        tasks: WorkItem list from scan_tasks().
        signals: SignalEntry list from scan_signals().
        graph_stats: dict from dep-analysis.py --graph-stats.
        docs_dir_str: effective docs directory path string.
        subproject: subproject query parameter value (e.g. "all" or "p1").

    Returns:
        dict with keys: subproject, docs_dir, generated_at, stats,
        critical_path, nodes, edges.
    """
    # dep-analysis.py returns both "fan_out" and "fan_out_map" (alias).
    # fan_in_map is injected locally by _handle_graph_api before calling here.
    fan_in_map: dict = graph_stats.get("fan_in_map", {})
    fan_out_map: dict = graph_stats.get("fan_out_map", {})
    critical_path: dict = graph_stats.get("critical_path", {"nodes": [], "edges": []})
    bottleneck_ids: list = graph_stats.get("bottleneck_ids", [])
    bottleneck_set: set = set(bottleneck_ids)
    cp_node_set = set(critical_path.get("nodes", []))

    # Derive per-task status and count stats
    status_counts = {"done": 0, "running": 0, "pending": 0, "failed": 0, "bypassed": 0}
    nodes = []
    task_id_set = {t.id for t in tasks}

    # Compute running_ids once (O(N+M)) — reuse same set for all nodes (no per-node scan)
    running_ids_set = _signal_set(signals, "running")

    for task in tasks:
        node_status = _derive_node_status(task, signals)
        status_counts[node_status] += 1

        # TSK-04-01 (FR-06): per-node data-phase attribute derivation
        _node_phase = _phase_data_attr(
            task.status,
            failed=(node_status == "failed"),
            bypassed=bool(task.bypassed),
        )

        nodes.append({
            "id": task.id,
            "label": task.title or task.id,
            "status": node_status,
            "is_critical": task.id in cp_node_set,
            "is_bottleneck": task.id in bottleneck_set,
            "fan_in": fan_in_map.get(task.id, 0),
            "fan_out": fan_out_map.get(task.id, 0),
            "bypassed": task.bypassed,
            "wp_id": task.wp_id,
            "depends": list(task.depends),
            # v4 payload fields (TSK-00-02)
            "phase_history_tail": _serialize_phase_history_tail_for_graph(
                task.phase_history_tail
            ),
            "last_event": task.last_event,
            "last_event_at": task.last_event_at,
            "elapsed_seconds": task.elapsed_seconds,
            "is_running_signal": task.id in running_ids_set,
            # TSK-05-02: filter predicate support fields
            "domain": task.domain if task.domain is not None else "-",
            "model": task.model if task.model is not None else "-",
            # TSK-04-01 (FR-06): data-phase attribute value for graph node
            "phase": _node_phase,
        })

    # Build edges from task depends relationships
    edges = []
    for task in tasks:
        for dep_id in task.depends:
            if dep_id in task_id_set:
                edges.append({"source": dep_id, "target": task.id})

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
