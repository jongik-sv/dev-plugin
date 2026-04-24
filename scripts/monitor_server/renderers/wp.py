"""monitor_server.renderers.wp — WP 카드 섹션 SSR 렌더러.

TSK-02-01 커밋 1: _section_wp_cards + _render_task_row_v2 호출 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import List, Optional

from ._util import (
    _esc,
    _t,
    _section_wrap,
    _empty_section,
    _resolve_heading,
    _group_preserving_order,
    _wp_card_counts,
    _wp_donut_style,
    _wp_donut_svg,
    _merge_badge,
)
from .taskrow import _render_task_row_v2


def _section_wp_cards(
    tasks,
    running_ids: set,
    failed_ids: set,
    heading: "Optional[str]" = None,
    wp_titles: "Optional[dict]" = None,
    lang: str = "ko",
    wp_merge_state: "Optional[dict]" = None,
) -> str:
    """WP card section: tasks grouped by wp_id, each WP as a v3 .wp card.

    v3 structure per card:
    - <details class="wp"> with <summary><div class="wp-head">:
      - .wp-donut: SVG stroke-dasharray donut + .pct overlay
      - .wp-title: .id badge + h3 (WP 제목) + .bar + .wp-counts
      - .wp-meta: total tasks count
    - <details class="wp-tasks"> body with .trow rows

    Empty tasks list → empty-state. Individual empty WP → empty-state per card.
    WP name XSS is escaped via ``_esc``.

    ``wp_titles`` ({WP-ID: title}) 이 주어지면 h3 에 WP 제목을 렌더하고,
    없으면 WP-ID 를 그대로 fallback 으로 사용한다 (design.html 대비 동작 유지).

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    heading = _resolve_heading("wp-cards", heading)
    if not tasks:
        return _empty_section("wp-cards", heading, "no tasks found — docs/tasks/ is empty")

    groups, order = _group_preserving_order(
        tasks, lambda item: getattr(item, "wp_id", None) or "WP-unknown"
    )
    wp_titles = wp_titles or {}

    blocks: List[str] = []
    for wp in order:
        wp_tasks = groups[wp]
        counts = _wp_card_counts(wp_tasks, running_ids, failed_ids)
        total = len(wp_tasks)
        done_count = counts["done"]
        pct_done = round(done_count / total * 100) if total > 0 else 0
        donut_style = _wp_donut_style(counts)

        svg_html = _wp_donut_svg(counts)
        donut_html = (
            f'<div class="wp-donut" style="{donut_style}" data-pct="{pct_done}%"'
            f' aria-label="{pct_done}% complete">\n'
            f'  {svg_html}\n'
            f'  <div class="pct">{pct_done}<small>PCT</small></div>\n'
            '</div>'
        )

        bar_html = (
            '<div class="bar" aria-hidden="true">'
            f'<div class="b-done" style="flex:{counts["done"]}"></div>'
            f'<div class="b-run"  style="flex:{counts["running"]}"></div>'
            f'<div class="b-fail" style="flex:{counts["failed"]}"></div>'
            f'<div class="b-byp"  style="flex:{counts["bypass"]}"></div>'
            f'<div class="b-pnd"  style="flex:{counts["pending"]}"></div>'
            '</div>'
        )

        # counts row
        counts_html = (
            '<div class="wp-counts">'
            f'<span class="c" data-k="done"><span class="sw"></span><b>{counts["done"]}</b> done</span>'
            f'<span class="c" data-k="run"><span class="sw"></span><b>{counts["running"]}</b> running</span>'
            f'<span class="c" data-k="pnd"><span class="sw"></span><b>{counts["pending"]}</b> pending</span>'
            f'<span class="c" data-k="fail"><span class="sw"></span><b>{counts["failed"]}</b> failed</span>'
            f'<span class="c" data-k="byp"><span class="sw"></span><b>{counts["bypass"]}</b> bypass</span>'
            '</div>'
        )

        wp_label = wp_titles.get(wp) or wp
        # 머지 준비도 뱃지 — wp_id 누락 시 현재 wp 값으로 보정
        _raw_ms = (wp_merge_state or {}).get(wp, {})
        _wp_ms = _raw_ms if _raw_ms.get("wp_id") else dict(_raw_ms, wp_id=wp)
        badge_html = _merge_badge(_wp_ms, lang)
        wp_title_html = (
            '<div class="wp-title wp-card-info">\n'
            '  <div class="row1" style="display:flex;align-items:center;gap:8px;">\n'
            f'    <span class="id">{_esc(wp)}</span>\n'
            f'    <h3 class="wp-card-title">{_esc(wp_label)}</h3>\n'
            f'    {badge_html}\n'
            '  </div>\n'
            f'  {bar_html}\n'
            f'  {counts_html}\n'
            '</div>'
        )

        wp_meta_html = f'<div class="wp-meta"><span class="big">{total} tasks</span></div>'

        wp_head_html = (
            '<div class="wp-head wp-card-header">\n'
            f'  {donut_html}\n'
            f'  {wp_title_html}\n'
            f'  {wp_meta_html}\n'
            '</div>'
        )

        task_rows = "\n".join(
            _render_task_row_v2(item, running_ids, failed_ids, lang=lang) for item in wp_tasks
        )
        card_body_html = (
            f'<details class="wp wp-tasks" data-wp="{_esc(wp)}" data-fold-key="{_esc(wp)}" data-fold-default-open open>\n'
            f'  <summary>{wp_head_html}<span class="ct">({total})</span></summary>\n'
            f'  <div class="task-list">\n{task_rows}\n  </div>\n'
            '</details>'
        ) if wp_tasks else f'<details class="wp" data-wp="{_esc(wp)}" data-fold-key="{_esc(wp)}"><p class="empty">no tasks</p></details>'
        blocks.append(card_body_html)

    return _section_wrap("wp-cards", heading, "\n".join(blocks))
