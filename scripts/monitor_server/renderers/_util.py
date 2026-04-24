"""monitor_server.renderers._util — 공용 유틸 재-export 경유지.

TSK-02-03: monitor_server.core 모듈에서 심볼을 직접 로드한다.
(이전: monitor-server.py를 monitor_server_entry 이름으로 동적 로드하던 방식에서 변경)

이 모듈은 renderers/* 서브모듈이 monitor_server.core의 공용 헬퍼를 import할 때
순환 참조를 방지하기 위한 경유지다.
"""

from __future__ import annotations

import sys
from monitor_server import core as _mod  # type: ignore[import]
from monitor_server import api as _api_mod  # type: ignore[import]

# 공용 유틸 재-export
# 각 심볼은 renderers/* 서브모듈에서 `from ._util import X` 로 사용한다.
_esc = _mod._esc
_t = _mod._t
# api.py가 SSOT인 4개 심볼 — core.py 중복 제거(C0-4) 선행 조건.
_signal_set = _api_mod._signal_set
_derive_node_status = _api_mod._derive_node_status
_serialize_phase_history_tail_for_graph = _api_mod._serialize_phase_history_tail_for_graph
_now_iso_z = _api_mod._now_iso_z
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
_PANE_PREVIEW_LINES = _mod._PANE_PREVIEW_LINES
_render_subagent_row = _mod._render_subagent_row
_SUBAGENT_INFO = _mod._SUBAGENT_INFO
_live_activity_rows = _mod._live_activity_rows
_render_arow = _mod._render_arow
_live_activity_details_wrap = _mod._live_activity_details_wrap

# taskrow.py 커밋 6(본문 이전) 이후 renderers/taskrow.py 로 이동 예정인 헬퍼들.
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

_iter_flat_entry_modules = _mod._iter_flat_entry_modules

# activity.py C1-4에서 필요한 헬퍼들
_parse_iso_utc = _mod._parse_iso_utc
_LIVE_ACTIVITY_LIMIT = _mod._LIVE_ACTIVITY_LIMIT
_SECTION_EYEBROWS = _mod._SECTION_EYEBROWS
_phase_of = _mod._phase_of
_KNOWN_PHASES = _mod._KNOWN_PHASES

# taskrow.py 선-shim이 _entry._phase_label 등에 접근할 수 있도록 _mod를 공개 심볼로 노출.
# taskrow.py의 `from ._util import _mod as _entry` 에서 사용된다.
