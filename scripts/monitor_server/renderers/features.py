"""monitor_server.renderers.features — Feature 섹션 SSR 렌더러.

core-renderer-split C2-3: _section_features 이전.
monitor_server/core.py 대응: 원본 함수 제거 후 thin wrapper로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional

from ._util import _resolve_heading, _empty_section, _section_wrap
from .taskrow import _render_task_row_v2


def _section_features(features, running_ids: set, failed_ids: set, heading: "Optional[str]" = None, lang: str = "ko") -> str:
    """Feature section: flat .trow list inside .features-wrap panel (no WP grouping).

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    heading = _resolve_heading("features", heading)
    if not features:
        return _empty_section(
            "features", heading, "no features found — docs/features/ is empty"
        )
    rows = "\n".join(
        _render_task_row_v2(item, running_ids, failed_ids, lang=lang) for item in features
    )
    return _section_wrap("features", heading, f'<div class="features-wrap">\n{rows}\n</div>')
