"""monitor_server.renderers.panel — 슬라이드 패널 DOM 스캐폴드 SSR 렌더러.

TSK-02-01 커밋 8: _drawer_skeleton 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
JS/CSS(_task_panel_js, _task_panel_css)는 S2/S3 소관이므로 본 모듈에서 제외.
"""

from __future__ import annotations


def _drawer_skeleton() -> str:
    """Return the v3 drawer scaffold HTML string.

    Structure:
      - div.drawer-backdrop[aria-hidden="true"] — click-outside close
      - aside.drawer[aria-hidden="true"] — slide-in panel with:
        - div.drawer-head — title + meta + close button
        - div.drawer-status — status indicator
        - pre.drawer-pre[tabindex="0"] — pane output content

    JS opens drawer via aria-hidden="false". Focus trap uses tabindex.
    """
    return (
        '<div class="drawer-backdrop" aria-hidden="true" data-drawer-backdrop></div>\n'
        '<aside class="drawer" role="dialog" aria-modal="true" aria-hidden="true"'
        ' aria-labelledby="drawer-title" data-drawer>\n'
        '  <div class="drawer-head" data-drawer-header>\n'
        '    <span class="drawer-title" id="drawer-title" data-drawer-title>Pane output</span>\n'
        '    <span class="drawer-meta" data-drawer-meta></span>\n'
        '    <button class="drawer-close" data-drawer-close'
        ' aria-label="Close drawer" tabindex="0">&#x2715;</button>\n'
        '  </div>\n'
        '  <div class="drawer-status" data-drawer-status></div>\n'
        '  <pre class="drawer-pre" data-drawer-pre data-drawer-body tabindex="0"></pre>\n'
        '</aside>'
    )
