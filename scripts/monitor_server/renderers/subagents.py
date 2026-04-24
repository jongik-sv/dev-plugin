"""monitor_server.renderers.subagents — Subagent 섹션 SSR 렌더러.

TSK-02-01 커밋 3: _section_subagents 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional

from ._util import (
    _section_wrap,
    _empty_section,
    _resolve_heading,
    _render_subagent_row,
    _SUBAGENT_INFO,
)


def _section_subagents(signals, heading: "Optional[str]" = None) -> str:
    """Subagent section: agent-pool signal slots grouped by scope.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    heading = _resolve_heading("subagents", heading)
    if not signals:
        return _section_wrap(
            "subagents",
            heading,
            f'  {_SUBAGENT_INFO}\n  <p class="empty">no agent-pool signals</p>',
        )

    pills = "\n".join(_render_subagent_row(sig) for sig in signals)
    subs_body = (
        f'  {_SUBAGENT_INFO}\n'
        f'  <div class="panel"><div class="subs">\n{pills}\n  </div></div>'
    )
    return _section_wrap("subagents", heading, subs_body)
