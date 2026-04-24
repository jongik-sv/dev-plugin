"""monitor_server.renderers — SSR 섹션 렌더러 패키지.

TSK-02-01에서 8개 섹션 렌더러 모듈을 점진 이전한다.
render_dashboard 본문 이전은 S5/S6 (후속 Task) 소관.

이 __init__.py는 재수출(re-export) 전용 — 로직 금지.
각 커밋에서 해당 모듈 이전 완료 후 import 라인을 활성화한다.

커밋 순서:
  커밋 0(pre): taskrow 선-shim 생성 (아래 첫 번째 import 활성화)
  커밋 1: wp.py 이전 + monitor-server.py shim 변환
  커밋 2: team.py 이전
  커밋 3: subagents.py 이전
  커밋 4: activity.py 이전
  커밋 5: depgraph.py 이전
  커밋 6: taskrow.py 본문 이전 (선-shim → 실제 함수)
  커밋 7: filterbar.py 이전
  커밋 8: panel.py 이전
"""

# taskrow는 커밋 0에서 선-shim으로 선행 생성됨 (wp/depgraph가 import하는 시점부터 필요)
from .taskrow import _phase_label, _phase_data_attr, _trow_data_status, _render_task_row_v2  # noqa: F401
from .wp import _section_wp_cards  # noqa: F401
from .team import _section_team  # noqa: F401
from .subagents import _section_subagents  # noqa: F401
from .activity import _section_live_activity  # noqa: F401
from .depgraph import _section_dep_graph, _build_graph_payload  # noqa: F401
from .filterbar import _section_filter_bar  # noqa: F401
from .panel import _drawer_skeleton  # noqa: F401

__all__ = [
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
]
