"""monitor_server.renderers.panel — 슬라이드 패널 DOM 스캐폴드 SSR 렌더러.

TSK-02-01 커밋 8: _drawer_skeleton 이전.
core-renderer-split C2-7: _render_pane_html + _render_pane_json 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
JS/CSS(_task_panel_js, _task_panel_css)는 S2/S3 소관이므로 본 모듈에서 제외.
"""

from __future__ import annotations

import html
import json

from ._util import get_static_version


def _render_pane_html(
    pane_id: str,
    payload: dict,
    *,
    refresh_seconds: int = 2,
) -> str:
    """Render a complete HTML document for the pane detail page.

    All user-derived strings are escaped with ``html.escape``. No external
    resources are loaded — CSS and JS are fully inline. The page uses vanilla
    JS ``setInterval + fetch`` for partial refresh (no ``<meta http-equiv=refresh>``).
    """
    escaped_id = html.escape(pane_id, quote=True)
    escaped_ts = html.escape(payload.get("captured_at") or "", quote=True)
    lines = payload.get("lines") or []
    escaped_lines = "\n".join(html.escape(ln, quote=True) for ln in lines)
    error_val = payload.get("error")
    error_block = (
        f'<p class="error">capture failed: {html.escape(str(error_val), quote=True)}</p>\n'
        if error_val is not None
        else ""
    )

    css_ver = get_static_version("style.css")
    js_ver = get_static_version("app.js")
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        f'  <title>pane {escaped_id}</title>\n'
        f'  <link rel="stylesheet" href="/static/style.css?v={css_ver}">\n'
        f'  <script src="/static/app.js?v={js_ver}" defer></script>\n'
        '</head>\n'
        '<body>\n'
        '<nav class="top-nav"><a href="/">&#x2190; back to dashboard</a></nav>\n'
        f'<h1>pane <code>{escaped_id}</code></h1>\n'
        f'{error_block}'
        f'<pre class="pane-capture" data-pane="{escaped_id}">{escaped_lines}</pre>\n'
        f'<div class="footer">captured at {escaped_ts}</div>\n'
        '</body>\n'
        '</html>\n'
    )


def _render_pane_json(payload: dict) -> bytes:
    """Serialize the pane payload dict to UTF-8 JSON bytes.

    ``line_count`` is always present (acceptance §3).
    """
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


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
