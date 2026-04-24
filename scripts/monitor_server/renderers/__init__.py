"""monitor_server.renderers — SSR 섹션 렌더러 패키지.

core-renderer-split (Phase 2) 완료 후 11개 렌더러 모듈이 이전됨.
render_dashboard 본문 이전은 Phase 3 소관.

이 __init__.py는 재수출(re-export) 전용 — 로직 금지.
"""

# Phase 1 (C1-x) 이전 모듈
from .taskrow import _phase_label, _phase_data_attr, _trow_data_status, _render_task_row_v2  # noqa: F401
from .wp import _section_wp_cards  # noqa: F401
from .team import _section_team  # noqa: F401
from .subagents import _section_subagents  # noqa: F401
from .activity import _section_live_activity  # noqa: F401
from .depgraph import _section_dep_graph, _build_graph_payload  # noqa: F401
from .filterbar import _section_filter_bar  # noqa: F401
from .panel import _drawer_skeleton, _render_pane_html, _render_pane_json  # noqa: F401

# Phase 2 (C2-x) 이전 모듈
from .header import _section_header, _section_sticky_header  # noqa: F401
from .kpi import _section_kpi, _kpi_counts, _spark_buckets, _kpi_spark_svg  # noqa: F401
from .features import _section_features  # noqa: F401
from .history import _section_phase_history, _status_class_for_phase  # noqa: F401
from .tabs import _section_subproject_tabs  # noqa: F401

__all__ = [
    # Phase 1
    "_section_wp_cards",
    "_section_team",
    "_section_subagents",
    "_section_live_activity",
    "_section_dep_graph",
    "_build_graph_payload",
    "_phase_label",
    "_phase_data_attr",
    "_trow_data_status",
    "_render_task_row_v2",
    "_section_filter_bar",
    "_drawer_skeleton",
    "_render_pane_html",
    "_render_pane_json",
    # Phase 2
    "_section_header",
    "_section_sticky_header",
    "_section_kpi",
    "_kpi_counts",
    "_spark_buckets",
    "_kpi_spark_svg",
    "_section_features",
    "_section_phase_history",
    "_status_class_for_phase",
    "_section_subproject_tabs",
]
