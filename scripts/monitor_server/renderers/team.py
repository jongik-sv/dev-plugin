"""monitor_server.renderers.team — Team 섹션 SSR 렌더러.

TSK-02-01 커밋 2: _section_team + pane 카드 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional

from ._util import (
    _esc,
    _section_wrap,
    _empty_section,
    _resolve_heading,
    _group_preserving_order,
    _pane_attr,
    _pane_last_n_lines,
    _render_pane_row,
    _TOO_MANY_PANES_THRESHOLD,
    _PANE_PREVIEW_LINES,
)


def _section_team(panes, heading: "Optional[str]" = None) -> str:
    """Team section: tmux panes + inline preview + expand button.

    When ``panes`` contains >= ``_TOO_MANY_PANES_THRESHOLD`` entries the
    preview is suppressed (``preview_lines=None``) to control subprocess cost.
    ``capture_pane()`` is the v1 implementation and is not called in that case.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    heading = _resolve_heading("team", heading)
    if panes is None:
        return _empty_section(
            "team",
            heading,
            "tmux not available on this host — Team section shows no data,"
            " other sections work normally.",
            css="info",
        )

    all_panes = list(panes)
    if not all_panes:
        return _empty_section("team", heading, "no tmux panes running")

    too_many = len(all_panes) >= _TOO_MANY_PANES_THRESHOLD

    groups, order = _group_preserving_order(
        all_panes, lambda pane: _pane_attr(pane, "window_name", None) or "(unnamed)"
    )

    blocks = []
    for window_name in order:
        row_parts = [
            _render_pane_row(
                pane,
                preview_lines=(
                    None if too_many
                    else _pane_last_n_lines(
                        _pane_attr(pane, "pane_id", ""),
                        n=_PANE_PREVIEW_LINES,
                    )
                ),
            )
            for pane in groups[window_name]
        ]
        rows = "\n".join(row_parts)
        blocks.append(
            '<details open>\n'
            f'  <summary>{_esc(window_name)} ({len(groups[window_name])} panes)</summary>\n'
            f'{rows}\n'
            '</details>'
        )

    team_body = '<div class="panel team">\n' + "\n".join(blocks) + '\n</div>'
    return _section_wrap("team", heading, team_body)
