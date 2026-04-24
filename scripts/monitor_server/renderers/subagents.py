"""monitor_server.renderers.subagents — Subagent 섹션 SSR 렌더러.

TSK-02-01 커밋 3: _section_subagents 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

core-renderer-split C1-3: _render_subagent_row + _SUBAGENT_INFO 본문 이전 (SSOT → 이 파일).

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional

from ._util import (
    _esc,
    _section_wrap,
    _resolve_heading,
)

_SUBAGENT_INFO = (
    '<p class="info">agent-pool subagents run inside the parent Claude session'
    ' — output capture is unavailable (signals only).</p>'
)


def _render_subagent_row(sig) -> str:
    """Render a single agent-pool slot as a v3 .sub pill with data-state."""
    kind = getattr(sig, "kind", "")
    task_id = getattr(sig, "task_id", "")

    # Map signal kind to data-state value.
    # bypassed signals are semantically "done" (bypassed = completed with bypass)
    state_map = {
        "running": "running",
        "done": "done",
        "failed": "failed",
        "bypassed": "done",
    }
    data_state = state_map.get(kind, "pending")

    return (
        f'<span class="sub" data-state="{data_state}">'
        f'<span class="sw"></span>'
        f'{_esc(task_id)}'
        f'<span class="n">{_esc(kind if kind else "?")}</span>'
        f'</span>'
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
