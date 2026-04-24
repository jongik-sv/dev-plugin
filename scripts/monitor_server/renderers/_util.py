"""monitor_server.renderers._util — 공용 유틸 재-export 경유지.

monitor-server.py (하이픈 파일명)의 공용 헬퍼를 renderers/* 에서 import할 때
순환 import를 방지하기 위해 importlib.util.spec_from_file_location으로
"monitor_server_entry" 이름으로 로드하여 패키지 이름 "monitor_server"와 격리한다.

TSK-02-01 S4 완료까지만 사용. S6(handlers.py 분리) 후 제거 예정.

주의: 이 shim은 test_monitor_render.py가
      spec_from_file_location("monitor_server", ...) 로 로드하는 것과
      이름공간이 분리되어 있으므로 충돌하지 않는다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ENTRY_MODULE_NAME = "monitor_server_entry"

if _ENTRY_MODULE_NAME not in sys.modules:
    _entry_path = Path(__file__).resolve().parent.parent.parent / "monitor-server.py"
    _spec = importlib.util.spec_from_file_location(_ENTRY_MODULE_NAME, str(_entry_path))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_ENTRY_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
else:
    _mod = sys.modules[_ENTRY_MODULE_NAME]

# 공용 유틸 재-export
# 각 심볼은 renderers/* 서브모듈에서 `from ._util import X` 로 사용한다.
# TSK-02-01 선-shim 기간 중 taskrow.py 미이전 함수들도 _mod 직접 참조로 노출.
_esc = _mod._esc
_t = _mod._t
_signal_set = _mod._signal_set
_normalize_lang = _mod._normalize_lang
_section_wrap = _mod._section_wrap
_empty_section = _mod._empty_section
_resolve_heading = _mod._resolve_heading
_group_preserving_order = _mod._group_preserving_order
_merge_badge = _mod._merge_badge
_wp_card_counts = _mod._wp_card_counts
_wp_donut_style = _mod._wp_donut_style
_wp_donut_svg = _mod._wp_donut_svg
_pane_attr = _mod._pane_attr
_pane_last_n_lines = _mod._pane_last_n_lines
_render_pane_row = _mod._render_pane_row
_TOO_MANY_PANES_THRESHOLD = _mod._TOO_MANY_PANES_THRESHOLD
_render_subagent_row = _mod._render_subagent_row
_SUBAGENT_INFO = _mod._SUBAGENT_INFO
_live_activity_rows = _mod._live_activity_rows
_render_arow = _mod._render_arow
_live_activity_details_wrap = _mod._live_activity_details_wrap
_derive_node_status = _mod._derive_node_status
_serialize_phase_history_tail_for_graph = _mod._serialize_phase_history_tail_for_graph
_now_iso_z = _mod._now_iso_z

# taskrow.py 커밋 6(본문 이전) 이후 renderers/taskrow.py 로 이동 예정인 헬퍼들.
# 현재는 taskrow.py 선-shim이 _mod 경유로 접근하므로 여기서 노출하지 않아도 동작하나,
# 후속 Task에서 _util.py 의존 코드가 이 심볼에 접근할 경우를 대비해 유지한다.
_wrap_with_data_section = _mod._wrap_with_data_section
_PHASE_LABELS = _mod._PHASE_LABELS
_PHASE_CODE_TO_ATTR = _mod._PHASE_CODE_TO_ATTR
_row_state_class = _mod._row_state_class
_format_elapsed = _mod._format_elapsed
_clean_title = _mod._clean_title
_retry_count = _mod._retry_count
_MAX_ESCALATION = _mod._MAX_ESCALATION
_encode_state_summary_attr = _mod._encode_state_summary_attr
_build_state_summary_json = _mod._build_state_summary_json

# taskrow.py 선-shim이 _entry._phase_label 등에 접근할 수 있도록 _mod를 공개 심볼로 노출.
# 이 변수명은 taskrow.py의 `from ._util import _mod as _entry` 에서 사용된다.
