"""monitor_server.renderers.team — Team 섹션 SSR 렌더러.

TSK-02-01 커밋 2: _section_team + pane 카드 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

core-renderer-split C1-2: _render_pane_row 본문 이전 (SSOT → 이 파일).

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from ._util import (
    _esc,
    _section_wrap,
    _empty_section,
    _resolve_heading,
    _group_preserving_order,
    _pane_attr,
    _pane_last_n_lines,
    _iter_flat_entry_modules,
    _TOO_MANY_PANES_THRESHOLD,
    _PANE_PREVIEW_LINES,
)


def _render_pane_row(pane, preview_lines: "Optional[str]" = "") -> str:
    """Render a single ``<div class="pane">`` for a tmux pane (v3 structure).

    v3: .pane > .pane-head (4-col grid) + .pane-preview.
    Still emits data-pane-expand for JS drawer + pane-row class for backward compat.

    Args:
        pane: PaneInfo dataclass or its dict form.
        preview_lines: Last-N-lines text to show in the preview ``<pre>``.
            - ``str`` (including empty string): renders
              ``<pre class="pane-preview">{preview_lines}</pre>``
            - ``None``: renders the "too many panes" placeholder
              ``<pre class="pane-preview empty">no preview (too many panes)</pre>``
    """
    pane_id_raw = _pane_attr(pane, "pane_id", "")
    pane_id_esc = _esc(pane_id_raw)
    pane_id_q = quote(pane_id_raw, safe="")
    cmd = _esc(_pane_attr(pane, "pane_current_command", ""))
    pid = _esc(_pane_attr(pane, "pane_pid", ""))
    window_name = _esc(_pane_attr(pane, "window_name", ""))

    # data-state: "live" for active panes, "idle" for shell-only
    data_state = "idle" if cmd in ("zsh", "bash", "sh") else "live"

    if preview_lines is None:
        preview_html = '<pre class="pane-preview empty">no preview (too many panes)</pre>'
    else:
        preview_html = f'<pre class="pane-preview">{_esc(preview_lines)}</pre>'

    return (
        f'<div class="pane" data-state="{data_state}">\n'
        f'  <div class="pane-head">\n'
        f'    <div class="name">{window_name}</div>\n'
        f'    <div class="meta">{pane_id_esc} · <span class="cmd">{cmd}</span> · pid {pid}</div>\n'
        f'    <a class="mini-btn" href="/pane/{pane_id_esc}" data-pane-url="/pane/{pane_id_q}">show output</a>\n'
        f'    <button class="mini-btn primary" type="button"'
        f' data-pane-expand="{pane_id_esc}"'
        f' aria-label="Expand pane {pane_id_esc}">expand <span class="kbd">&#x21B5;</span></button>\n'
        f'  </div>\n'
        f'{preview_html}\n'
        '</div>'
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

    # Honour mock.patch.object(flat_entry, "_pane_last_n_lines", ...) from tests.
    # Multiple flat-load copies of monitor-server.py can coexist in sys.modules
    # (e.g. monitor_server_pane_size AND monitor_server_dep_graph_summary), each
    # holding a different function object from a different monitor_server_core_impl
    # load. We must pick only a genuine test mock, not an alternate core function.
    # Real core functions always have __qualname__ == "_pane_last_n_lines";
    # MagicMock / lambda / side_effect substitutes do not set __qualname__.
    _last_n = _pane_last_n_lines
    for _entry in _iter_flat_entry_modules():
        _fn = getattr(_entry, "_pane_last_n_lines", None)
        if _fn is None or _fn is _pane_last_n_lines:
            continue
        # Reject alternate core function copies (same qualname = real function)
        if getattr(_fn, "__qualname__", None) == "_pane_last_n_lines":
            continue
        _last_n = _fn
        break

    blocks = []
    for window_name in order:
        row_parts = [
            _render_pane_row(
                pane,
                preview_lines=(
                    None if too_many
                    else _last_n(
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
