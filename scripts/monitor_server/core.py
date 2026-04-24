"""monitor_server.core — dev-monitor 통합 모듈 + facade.

core-decomposition (Phase 0 + Phase 1) 결과 본 모듈은 **facade 역할**과
**HTTP 핸들러/렌더러 구현**을 함께 담는다. 대부분의 도메인 로직은 전용
서브모듈로 이관되었고 core.py 는 해당 심볼을 재-export 하여 기존
``import monitor_server.core as core`` 패턴의 backward-compat 을 보장한다.

하위 서브모듈 (Phase 1 분리):
- :mod:`monitor_server.caches`    — TTL 캐시 + ETag 캐시 lazy-load
- :mod:`monitor_server.signals`   — 시그널 파일 스캔 + WP busy 집계
- :mod:`monitor_server.panes`     — tmux pane 메타데이터 + capture
- :mod:`monitor_server.workitems` — Task/Feature 스캔, worktree 집계, 서브프로젝트
- :mod:`monitor_server.api`       — /api/* 엔드포인트 공용 유틸 (Phase 0에서 SSOT 승격)

core.py 에 남은 주요 구성 요소 (Phase 2 후보):
- HTTP 서버: ``MonitorHandler``, ``run_server()``
- 라우팅: ``/`` (대시보드), ``/pane/{id}`` (HTML), ``/api/pane/{id}`` (JSON),
  ``/api/state`` (전체 스냅샷)
- HTML 렌더러: ``_render_*``, ``DASHBOARD_CSS``
- 상태 모델 공용 유틸: ``_phase_data_attr``, ``_phase_label`` 등

facade 계약:
- ``core._SIGNALS_CACHE``, ``core._TTLCache``, ``core.scan_signals`` 등
  서브모듈 심볼은 **import 시점 바인딩** 으로 재-export 된다.
- 테스트가 ``core._X`` 를 monkey-patch 하더라도 서브모듈 내부 이름 참조는
  서브모듈 namespace 를 본다. 따라서 캐시/함수 monkey-patch 는 대상 서브모듈
  경유로 수행해야 한다 (design.md §4.1 Option A).
- ``__all__`` 은 선언하지 않는다 — 외부 ``from monitor_server.core import *``
  호환성을 유지하기 위해.

구현 원칙:
- Python 3.8+ stdlib 전용 (``CLAUDE.md`` 규약)
- 모든 ``subprocess.run`` 은 ``shell=False`` 리스트 인자 + 명시 ``timeout``
- 모든 실패 경로는 정의된 반환 값으로 흡수 — 예외는
  ``capture_pane`` 의 pane_id 형식 위반(ValueError)만 허용
- pane_id URL 인코딩: 링크 생성 시 ``quote(pane_id, safe="")``, 라우터에서
  ``unquote(path_segment)`` 후 ``_PANE_ID_RE`` 검증
- flat-load 컨텍스트(test 에서 monitor-server.py 를 monitor_server 이름으로
  로드하는 경우)도 지원 — 모든 서브모듈 import 는 try/except 로
  ``_c1_bootstrap_submodules()`` fallback 을 가진다.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil  # noqa: F401 — tests patch via `MS.shutil.which` (see test_monitor_tmux.py). 제거 시 AttributeError.
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlsplit

# [core-decomposition:C1-6] 정적 타입 체커용 import.
# signals/panes/workitems 의 심볼은 아래 try/except 패턴으로 런타임 재-export 되지만,
# Pylance 는 except 분기(`X = _cXX_mod.X`)를 Any 로 좁혀 "형식 식에는 변수를 사용할 수
# 없습니다" 경고를 낸다. TYPE_CHECKING 블록은 런타임에 평가되지 않고 타입 체커에게만
# 정적 클래스 참조를 제공하여 타입 힌트에서 안전하게 쓰이게 한다.
if TYPE_CHECKING:
    from monitor_server.panes import PaneInfo
    from monitor_server.signals import SignalEntry
    from monitor_server.workitems import PhaseEntry, WorkItem

if not sys.pycache_prefix:
    sys.pycache_prefix = "/tmp/codex-pycache"

# ---------------------------------------------------------------------------
# [core-decomposition:C0-4] api.py SSOT import — 8개 중복 함수 재-export
# ---------------------------------------------------------------------------
# core.py에 있던 _signal_set, _serialize_phase_history_tail_for_graph,
# _derive_node_status, _build_graph_payload, _build_fan_in_map, _load_state_json,
# _build_task_detail_payload, _now_iso_z 는 api.py로 단일화되었다.
# 본 모듈은 backward-compat을 위해 재-export하며, 신규 호출은 api.py 직접 사용 권장.
#
# flat-load 컨텍스트(test에서 monitor-server.py를 monitor_server 이름으로 로드하는
# 경우) 대응: `from monitor_server.api import ...`가 실패하면 spec_from_file_location
# 으로 api.py를 직접 로드한다. 이렇게 해야 monitor-server.py의 _load_core_module이
# fallback 경로로 core.py를 파일 로드할 때도 8개 심볼이 정상 바인딩된다.
try:
    from monitor_server.api import (  # noqa: F401,E402
        _signal_set,
        _serialize_phase_history_tail_for_graph,
        _derive_node_status,
        _build_graph_payload,
        _build_fan_in_map,
        _load_state_json,
        _build_task_detail_payload,
        _now_iso_z,
    )
except (ImportError, ModuleNotFoundError):
    import importlib.util as _c04_ilu  # type: ignore
    _c04_api_path = Path(__file__).resolve().parent / "api.py"
    _c04_spec = _c04_ilu.spec_from_file_location("monitor_server_api_c0_4", _c04_api_path)
    _c04_mod = _c04_ilu.module_from_spec(_c04_spec)
    sys.modules.setdefault("monitor_server_api_c0_4", _c04_mod)
    _c04_spec.loader.exec_module(_c04_mod)  # type: ignore[union-attr]
    _signal_set = _c04_mod._signal_set
    _serialize_phase_history_tail_for_graph = _c04_mod._serialize_phase_history_tail_for_graph
    _derive_node_status = _c04_mod._derive_node_status
    _build_graph_payload = _c04_mod._build_graph_payload
    _build_fan_in_map = _c04_mod._build_fan_in_map
    _load_state_json = _c04_mod._load_state_json
    _build_task_detail_payload = _c04_mod._build_task_detail_payload
    _now_iso_z = _c04_mod._now_iso_z

# ---------------------------------------------------------------------------
# [core-decomposition:C1-1/C1-2] caches + signals 모듈 재-export
# ---------------------------------------------------------------------------
# flat-load 컨텍스트(scripts/monitor-server.py 를 'monitor_server' 이름으로 로드한
# 테스트)에서 'monitor_server.caches' 같은 dotted import 는 실패한다.
# 이 fallback 은 caches.py / signals.py 를 파일로 로드한 뒤 sys.modules 의
# 정규 키('monitor_server.caches', 'monitor_server.signals')에 등록하여
# signals.py 내부의 `from monitor_server.caches import _SIGNALS_CACHE` 같은
# 하위 import 가 정상 동작하게 만든다. 이렇게 해야 core/signals 두 경로에서
# 동일한 _SIGNALS_CACHE 인스턴스가 공유된다.

def _c1_bootstrap_submodules():
    """flat-load 환경에서 분해 submodule(caches/signals/panes/workitems)을 pre-populate."""
    import importlib.util as _ilu
    pkg_dir = Path(__file__).resolve().parent
    for submod_name, fname in (
        ("caches", "caches.py"),
        ("signals", "signals.py"),
        ("panes", "panes.py"),
        ("workitems", "workitems.py"),
    ):
        key = f"monitor_server.{submod_name}"
        if sys.modules.get(key) is not None:
            continue
        path = pkg_dir / fname
        if not path.exists():
            continue
        spec = _ilu.spec_from_file_location(key, str(path))
        if spec is None:
            continue
        mod = _ilu.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]


try:
    from monitor_server.caches import (  # noqa: F401,E402
        _TTLCache,
        _SIGNALS_CACHE,
        _GRAPH_CACHE,
        _ensure_etag_cache,
    )
    # _compute_etag / _check_if_none_match 은 module-level globals로 lazy-load 되므로
    # 속성 접근 시점마다 caches 모듈을 경유해야 한다. core.py 내부 호출자는
    # _ensure_etag_cache() 호출 후 caches 모듈에서 다시 읽는다.
    import monitor_server.caches as _caches_mod  # noqa: E402
except (ImportError, ModuleNotFoundError):
    _c1_bootstrap_submodules()
    _caches_mod = sys.modules["monitor_server.caches"]
    _TTLCache = _caches_mod._TTLCache
    _SIGNALS_CACHE = _caches_mod._SIGNALS_CACHE
    _GRAPH_CACHE = _caches_mod._GRAPH_CACHE
    _ensure_etag_cache = _caches_mod._ensure_etag_cache


def _compute_etag(*args, **kwargs):  # type: ignore[no-redef]
    """Shim: etag_cache lazy-load 후 실제 구현 호출 (caches 모듈 경유)."""
    fn = getattr(_caches_mod, "_compute_etag", None)
    if fn is None:
        return None
    return fn(*args, **kwargs)


def _check_if_none_match(*args, **kwargs):  # type: ignore[no-redef]
    """Shim: etag_cache lazy-load 후 실제 구현 호출 (caches 모듈 경유)."""
    fn = getattr(_caches_mod, "_check_if_none_match", None)
    if fn is None:
        return None
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# [core-decomposition:C1-2] signals 모듈 재-export
# ---------------------------------------------------------------------------
# SignalEntry, scan_signals*, _walk_signal_entries, _wp_busy_set, 신호 관련
# 상수는 signals.py 로 이관되었다. core.py facade 에서는 재-export만 수행.
try:
    from monitor_server.signals import (  # noqa: F401,E402
        SignalEntry,
        _iso_mtime,
        _signal_entry,
        _walk_signal_entries,
        scan_signals,
        scan_signals_cached,
        _wp_busy_set,
        _SIGNAL_KINDS,
        _AGENT_POOL_DIR_PREFIX,
        _AGENT_POOL_SCOPE_PREFIX,
        _WP_SIGNAL_PREFIX_RE,
        _WP_ID_RE,
    )
except (ImportError, ModuleNotFoundError):
    _c1_bootstrap_submodules()
    _c12_mod = sys.modules["monitor_server.signals"]
    SignalEntry = _c12_mod.SignalEntry
    _iso_mtime = _c12_mod._iso_mtime
    _signal_entry = _c12_mod._signal_entry
    _walk_signal_entries = _c12_mod._walk_signal_entries
    scan_signals = _c12_mod.scan_signals
    scan_signals_cached = _c12_mod.scan_signals_cached
    _wp_busy_set = _c12_mod._wp_busy_set
    _SIGNAL_KINDS = _c12_mod._SIGNAL_KINDS
    _AGENT_POOL_DIR_PREFIX = _c12_mod._AGENT_POOL_DIR_PREFIX
    _AGENT_POOL_SCOPE_PREFIX = _c12_mod._AGENT_POOL_SCOPE_PREFIX
    _WP_SIGNAL_PREFIX_RE = _c12_mod._WP_SIGNAL_PREFIX_RE
    _WP_ID_RE = _c12_mod._WP_ID_RE

# ---------------------------------------------------------------------------
# [core-decomposition:C1-3] panes 모듈 재-export
# ---------------------------------------------------------------------------
try:
    from monitor_server.panes import (  # noqa: F401,E402
        PaneInfo,
        list_tmux_panes,
        capture_pane,
        _TMUX_FMT,
        _PANE_ID_RE,
        _CAPTURE_PANE_SCROLLBACK,
        _LIST_PANES_TIMEOUT,
        _CAPTURE_PANE_TIMEOUT,
    )
except (ImportError, ModuleNotFoundError):
    _c1_bootstrap_submodules()
    _c13_mod = sys.modules["monitor_server.panes"]
    PaneInfo = _c13_mod.PaneInfo
    list_tmux_panes = _c13_mod.list_tmux_panes
    capture_pane = _c13_mod.capture_pane
    _TMUX_FMT = _c13_mod._TMUX_FMT
    _PANE_ID_RE = _c13_mod._PANE_ID_RE
    _CAPTURE_PANE_SCROLLBACK = _c13_mod._CAPTURE_PANE_SCROLLBACK
    _LIST_PANES_TIMEOUT = _c13_mod._LIST_PANES_TIMEOUT
    _CAPTURE_PANE_TIMEOUT = _c13_mod._CAPTURE_PANE_TIMEOUT

# CSI-style ANSI escape sequences (color, cursor, etc.).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# pane-preview last-N lines — single source of truth shared by
# ``_pane_last_n_lines`` default, ``_section_team`` call-site, CSS ``max-height``
# (1.5em * 6 = 9em), and the ``::before`` "last 6 lines" label.
_PANE_PREVIEW_LINES = 6

# ---------------------------------------------------------------------------
# Static file serving constants (TSK-03-03)
# ---------------------------------------------------------------------------

_STATIC_PATH_PREFIX = "/static/"

# Whitelist of allowed filenames under /static/.
# - vendor JS (5): served from plugin_root/skills/dev-monitor/vendor/
# - local bundles (2): style.css + app.js, served in-memory by handlers (see get_static_bundle)
# graph-client.js is a TSK-03-04 placeholder committed as an empty file.
_STATIC_WHITELIST: "frozenset[str]" = frozenset({
    "cytoscape.min.js",
    "dagre.min.js",
    "cytoscape-node-html-label.min.js",
    "cytoscape-dagre.min.js",
    "graph-client.js",
    "style.css",
    "app.js",
})


# ---------------------------------------------------------------------------
# [core-decomposition:C1-4] workitems 모듈 재-export
# ---------------------------------------------------------------------------
# (TRD §5.2 SignalEntry → monitor_server.signals (C1-2))
# (TRD §5.3 PaneInfo/list_tmux_panes/capture_pane → monitor_server.panes (C1-3))
try:
    from monitor_server.workitems import (  # noqa: F401,E402
        PhaseEntry,
        WorkItem,
        _cap_error,
        _read_state_json,
        _normalize_elapsed,
        _build_phase_history_tail,
        _load_wbs_title_map,
        _load_wbs_wp_titles,
        _load_feature_title,
        _make_workitem_from_error,
        _make_workitem_from_state,
        _make_workitem_placeholder,
        _resolve_abs_path,
        _scan_dir,
        scan_tasks,
        scan_features,
        _discover_worktree_docs,
        _workitem_updated_key,
        _merge_workitems_newest_wins,
        _dedup_workitems_by_id,
        _aggregated_scan,
        scan_tasks_aggregated,
        scan_features_aggregated,
        discover_subprojects,
        _filter_by_subproject,
        _MAX_STATE_BYTES,
        _PHASE_TAIL_LIMIT,
        _ERROR_CAP,
        _WBS_WP_RE,
        _WBS_TSK_RE,
    )
except (ImportError, ModuleNotFoundError):
    _c1_bootstrap_submodules()
    _c14_mod = sys.modules["monitor_server.workitems"]
    PhaseEntry = _c14_mod.PhaseEntry
    WorkItem = _c14_mod.WorkItem
    _cap_error = _c14_mod._cap_error
    _read_state_json = _c14_mod._read_state_json
    _normalize_elapsed = _c14_mod._normalize_elapsed
    _build_phase_history_tail = _c14_mod._build_phase_history_tail
    _load_wbs_title_map = _c14_mod._load_wbs_title_map
    _load_wbs_wp_titles = _c14_mod._load_wbs_wp_titles
    _load_feature_title = _c14_mod._load_feature_title
    _make_workitem_from_error = _c14_mod._make_workitem_from_error
    _make_workitem_from_state = _c14_mod._make_workitem_from_state
    _make_workitem_placeholder = _c14_mod._make_workitem_placeholder
    _resolve_abs_path = _c14_mod._resolve_abs_path
    _scan_dir = _c14_mod._scan_dir
    scan_tasks = _c14_mod.scan_tasks
    scan_features = _c14_mod.scan_features
    _discover_worktree_docs = _c14_mod._discover_worktree_docs
    _workitem_updated_key = _c14_mod._workitem_updated_key
    _merge_workitems_newest_wins = _c14_mod._merge_workitems_newest_wins
    _dedup_workitems_by_id = _c14_mod._dedup_workitems_by_id
    _aggregated_scan = _c14_mod._aggregated_scan
    scan_tasks_aggregated = _c14_mod.scan_tasks_aggregated
    scan_features_aggregated = _c14_mod.scan_features_aggregated
    discover_subprojects = _c14_mod.discover_subprojects
    _filter_by_subproject = _c14_mod._filter_by_subproject
    _MAX_STATE_BYTES = _c14_mod._MAX_STATE_BYTES
    _PHASE_TAIL_LIMIT = _c14_mod._PHASE_TAIL_LIMIT
    _ERROR_CAP = _c14_mod._ERROR_CAP
    _WBS_WP_RE = _c14_mod._WBS_WP_RE
    _WBS_TSK_RE = _c14_mod._WBS_TSK_RE




# ---------------------------------------------------------------------------
# HTML dashboard rendering (TSK-01-04)
# ---------------------------------------------------------------------------

_DEFAULT_REFRESH_SECONDS = 3
_PHASES_SECTION_LIMIT = 10
_ERROR_TITLE_CAP = 200
_SECTION_ANCHORS = ("wp-cards", "features", "team", "subagents", "activity", "phases", "dep-graph")

# ---------------------------------------------------------------------------
# i18n (TSK-03-04) — minimal table; other sections adopt as follow-on Tasks
# ---------------------------------------------------------------------------

_I18N: dict[str, dict[str, str]] = {
    "ko": {
        "work_packages": "작업 패키지",
        "features": "기능",
        "team_agents": "팀 에이전트 (tmux)",
        "subagents": "서브 에이전트 (agent-pool)",
        "live_activity": "실시간 활동",
        "dep_graph": "의존성 그래프",
        # dep-graph summary chip labels
        "dep_stat_total":    "총",
        "dep_stat_done":     "완료",
        "dep_stat_running":  "진행",
        "dep_stat_pending":  "대기",
        "dep_stat_failed":   "실패",
        "dep_stat_bypassed": "바이패스",
        "dep_wheel_zoom":    "휠 줌",
        # DDTR phase badge labels (ko/en same label — keys separated for i18n extensibility)
        "phase_design":  "Design",
        "phase_build":   "Build",
        "phase_test":    "Test",
        "phase_done":    "Done",
        "phase_failed":  "Failed",
        "phase_bypass":  "Bypass",
        "phase_pending": "Pending",
    },
    "en": {
        "work_packages": "Work Packages",
        "features": "Features",
        "team_agents": "Team Agents (tmux)",
        "subagents": "Subagents (agent-pool)",
        "live_activity": "Live Activity",
        "dep_graph": "Dependency Graph",
        # dep-graph summary chip labels
        "dep_stat_total":    "Total",
        "dep_stat_done":     "Done",
        "dep_stat_running":  "Running",
        "dep_stat_pending":  "Pending",
        "dep_stat_failed":   "Failed",
        "dep_stat_bypassed": "Bypassed",
        "dep_wheel_zoom":    "Wheel zoom",
        # DDTR phase badge labels (ko/en same label — keys separated for i18n extensibility)
        "phase_design":  "Design",
        "phase_build":   "Build",
        "phase_test":    "Test",
        "phase_done":    "Done",
        "phase_failed":  "Failed",
        "phase_bypass":  "Bypass",
        "phase_pending": "Pending",
    },
}


def _normalize_lang(lang: str) -> str:
    """lang 정규화 헬퍼. ko/en 이외의 값은 'ko'로 폴백."""
    return lang if lang in _I18N else "ko"


def _t(lang: str, key: str) -> str:
    """Return i18n string for *key* in *lang*.

    Fallback chain: requested lang → "ko" → key itself.
    Never raises.
    """
    return (
        _I18N.get(_normalize_lang(lang), {}).get(key)
        or _I18N.get("ko", {}).get(key)
        or key
    )


# ---------------------------------------------------------------------------
# DDTR phase badge helpers
# ---------------------------------------------------------------------------

# Maps status code / virtual keys → i18n key in _I18N.
# Keys: DDTR status codes + virtual keys (failed / bypass / pending).
_PHASE_LABELS: "dict[str, dict[str, str]]" = {
    "[dd]":    {"ko": "Design",  "en": "Design"},
    "[im]":    {"ko": "Build",   "en": "Build"},
    "[ts]":    {"ko": "Test",    "en": "Test"},
    "[xx]":    {"ko": "Done",    "en": "Done"},
    "failed":  {"ko": "Failed",  "en": "Failed"},
    "bypass":  {"ko": "Bypass",  "en": "Bypass"},
    "pending": {"ko": "Pending", "en": "Pending"},
}

# Maps status code → data-phase attribute value (raw string without brackets).
_PHASE_CODE_TO_ATTR: "dict[str, str]" = {
    "[dd]": "dd",
    "[im]": "im",
    "[ts]": "ts",
    "[xx]": "xx",
    # Direct string aliases for override states (graph SSR emits these via
    # _derive_node_status; test_monitor_phase_tokens.py also passes them raw).
    # Bracket-less phase codes ("dd", "im", ...) intentionally stay unmapped.
    "failed": "failed",
    "bypass": "bypass",
    "pending": "pending",
}


def _phase_label(status_code: "Optional[str]", lang: str, *, failed: bool, bypassed: bool) -> str:  # type: ignore[override]  # noqa: F811
    """Return human-readable badge label for a Task row.

    Priority: bypassed > failed > status_code mapping > pending.
    lang is normalised via _normalize_lang (unknown → 'ko').

    Note: there is a legacy _phase_label(status_str) function defined later
    (used for task-detail history rows). This function shadows it at module
    level for badge usage; the legacy function is renamed internally and not
    exposed as a public helper.
    """
    normalised = _normalize_lang(lang)
    if bypassed:
        return _PHASE_LABELS["bypass"].get(normalised) or _PHASE_LABELS["bypass"]["ko"]
    if failed:
        return _PHASE_LABELS["failed"].get(normalised) or _PHASE_LABELS["failed"]["ko"]
    code = str(status_code).strip() if status_code else ""
    entry = _PHASE_LABELS.get(code)
    if entry:
        return entry.get(normalised) or entry["ko"]
    return _PHASE_LABELS["pending"].get(normalised) or _PHASE_LABELS["pending"]["ko"]


def _phase_data_attr(status_code: "Optional[str]", *, failed: bool = False, bypassed: bool = False) -> str:
    """Return the data-phase attribute value for a Task row .trow element.

    Priority: bypassed > failed > status_code mapping > pending.
    """
    if bypassed:
        return "bypass"
    if failed:
        return "failed"
    code = str(status_code).strip() if status_code else ""
    return _PHASE_CODE_TO_ATTR.get(code, "pending")


# Status → (emoji, label, css_class) for the non-override branch of
# ``_status_badge``. The bypass/failed/running overrides stay inline in the
# function because they depend on boolean flags, not ``status``.
_STATUS_BADGE_MAP = {
    "[dd]": ("🔵", "DESIGN", "badge-dd"),
    "[im]": ("🟣", "BUILD", "badge-im"),
    "[ts]": ("🟢", "TEST", "badge-ts"),
    "[xx]": ("✅", "DONE", "badge-xx"),
}
_STATUS_BADGE_DEFAULT = ("⚪", "PENDING", "badge-pending")


DASHBOARD_CSS = """
/* ---------- v3 design system ---------- */
/* fonts: fonts.googleapis.com — JetBrains Mono, Space Grotesk (loaded via preconnect) */

/* ---------- tokens ---------- */
:root{
  /* surfaces */
  --bg: #0b0d10;
  --bg-1: #0f1216;
  --bg-2: #141820;
  --bg-3: #1a1f28;
  --line: #1f2530;
  --line-2: #2a3140;
  --line-hi: #3a4456;

  /* text */
  --ink: #e8ecf1;
  --ink-2: #aeb5c1;
  --ink-3: #6b7480;
  --ink-4: #464e5a;

  /* accents */
  --accent: #c89b6a;
  --accent-hi: #e6b884;
  --accent-dim: #7a5e3f;

  /* phase palette */
  --run: #4aa3ff;
  --run-glow: rgba(74,163,255,.18);
  --done: #4ed08a;
  --done-glow: rgba(78,208,138,.16);
  --fail: #ff5d5d;
  --fail-glow: rgba(255,93,93,.16);
  --bypass: #d16be0;
  --bypass-glow: rgba(209,107,224,.16);
  --pending: #f0c24a;
  --pending-glow: rgba(240,194,74,.16);
  --critical: #f59e0b;
  --critical-glow: rgba(245,158,11,.18);

  /* phase tokens (FR-06) — WCAG AA contrast on --bg-2 (#141820):
     dd indigo ≈5.1:1, im sky ≈5.3:1, ts violet ≈5.0:1, xx emerald ≈4.7:1,
     failed red ≈4.6:1, bypass amber ≈6.8:1, pending gray ≈4.5:1 */
  --phase-dd: #6366f1;
  --phase-im: #0ea5e9;
  --phase-ts: #a855f7;
  --phase-xx: #10b981;
  --phase-failed: #ef4444;
  --phase-bypass: #f59e0b;
  --phase-pending: #6b7280;
  --critical: #f59e0b;

  /* type */
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: "Space Grotesk", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --display: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;

  --radius: 4px;
  --radius-lg: 6px;

  /* font size */
  --font-body: 14px;
  --font-mono: 14px;
  --font-h2: 17px;
  --font-pct: 15px;
}

/* ---------- reset ---------- */
*,*::before,*::after{ box-sizing:border-box; }
html,body{ margin:0; padding:0; }
body{
  background: var(--bg);
  color: var(--ink);
  font-family: var(--mono);
  font-size: var(--font-body);
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  letter-spacing: 0.01em;
  min-height: 100vh;
  /* monitor-perf (2026-04-24): 전체 뷰포트 고정 배경(fixed attach) + 대형 radial-gradient 2개 제거 —
     스크롤/리페인트마다 전체 뷰포트 재합성을 강제하던 장식 레이어. 기능 영향 없음. */
}
/* monitor-perf (2026-04-24): body::before 스캔라인 블렌드 오버레이 완전 제거 —
   위치 고정 요소가 반복 그라디언트와 블렌드 모드(overlay)로 뷰포트 전체를
   매 프레임 픽셀 단위로 합성하여 Chrome GPU 30~50%를 단독 소모. 장식이므로 기능 무관. */
/* monitor-perf (2026-04-24): 무한 애니메이션 일괄 정지 가드 —
   탭 hidden 또는 사용자 토글 시 app.js가 :root[data-anim="off"]를 설정해 GPU/compositor 완전 idle. */
:root[data-anim="off"] *,
:root[data-anim="off"] *::before,
:root[data-anim="off"] *::after {
  animation: none !important;
  transition: none !important;
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
button{ font: inherit; color: inherit; background:none; border:0; cursor:pointer; }
a{ color: inherit; }
summary{ cursor: pointer; list-style: none; }
summary::-webkit-details-marker{ display:none; }
:where(button,summary,[tabindex]):focus-visible{
  outline: 1px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}

/* ---------- layout shell ---------- */
.shell{
  position: relative;
  z-index: 2;
  max-width: none;
  margin: 0;
  padding: 0 24px 0;
}

/* ---------- 1. Command Bar ---------- */
.cmdbar{
  position: sticky; top:0; z-index: 30;
  height: 52px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  padding: 0 20px;
  margin: 0 -20px;
  /* monitor-perf: 블러 합성 제거 — Chrome GPU 20~40% 단독 소모. 투명도 0.88→0.96으로 가독 보전. */
  background: rgba(11,13,16,0.96);
  border-bottom: 1px solid var(--line);
}
.cmdbar::after{
  content:""; position:absolute; inset:auto 0 -1px 0; height:1px;
  background: linear-gradient(90deg, transparent, var(--accent-dim) 40%, var(--accent-dim) 60%, transparent);
  opacity:.5;
}
.cmdbar .lang-toggle,
.cmdbar .top-nav{
  display:inline-flex; align-items:center; gap: 4px;
  font-family: var(--mono);
  font-size: 11px; letter-spacing: .04em;
  color: var(--ink-3);
}
.cmdbar .top-nav{ gap: 2px; }
.cmdbar .lang-toggle a,
.cmdbar .top-nav a{
  display:inline-flex; align-items:center;
  height: 22px; padding: 0 7px;
  border: 1px solid transparent;
  border-radius: 3px;
  color: var(--ink-3);
  text-decoration: none;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: .06em;
  transition: color .15s, border-color .15s, background .15s;
}
.cmdbar .lang-toggle a:hover,
.cmdbar .top-nav a:hover{
  color: var(--ink);
  border-color: var(--line-2);
  background: var(--bg-2);
}
.cmdbar .top-nav a{ font-size: 10px; padding: 0 6px; }
.brand{
  display:flex; align-items:center; gap:10px;
  font-family: var(--display);
  font-weight: 600; letter-spacing: .04em; text-transform: uppercase; font-size: 12px;
}
.brand .logo{
  width: 22px; height: 22px;
  display:grid; place-items:center;
  color: var(--accent);
}
.brand .logo svg{ width: 22px; height: 22px; }
.brand .title{ color: var(--ink); }
.brand .slash{ color: var(--ink-4); margin: 0 2px; }
.brand .sub{ color: var(--ink-3); font-weight: 400; text-transform:none; letter-spacing: 0; font-size: 12px; }

.cmdbar .meta{
  display:flex; align-items:center; gap: 20px;
  color: var(--ink-3);
  font-size: 12px;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.cmdbar .meta .k{ color: var(--ink-4); margin-right: 6px; }
.cmdbar .meta .v{ color: var(--ink-2); }
.cmdbar .meta .path{ color: var(--accent); }
.cmdbar .meta .dot{ color: var(--line-hi); margin: 0 8px; }

.cmdbar .actions{ display:flex; align-items:center; gap: 8px; }

.pulse{
  display:inline-flex; align-items:center; gap:8px;
  color: var(--done);
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  font-weight: 600;
}
.pulse .dot{
  /* monitor-perf (2026-04-24): LIVE 인디케이터의 항상-켜진 infinite 애니메이션 제거 —
     대시보드 유휴 시에도 계속 컴포지터를 깨워 GPU 2~3% 상시 소모. "LIVE" 텍스트로
     이미 상태를 표현하므로 정적 도트 + 부드러운 그림자로 충분. */
  width:8px; height:8px; border-radius: 50%;
  background: var(--done);
  box-shadow: 0 0 4px 0 var(--done-glow);
}
/* shared spinner — TSK-00-01 contract; .node-spinner shares the same animation (TSK-02-04 dep-node spinner) */
@keyframes spin{ to{ transform: rotate(360deg); } }
.spinner,.node-spinner{
  display: none;
  width: 10px; height: 10px;
  border: 2px solid transparent;
  border-top-color: var(--run);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  vertical-align: middle;
}
.badge .spinner{ margin-left: 4px; }
/* TSK-04-01 (FR-06): inline spinner lives inside the badge; default hidden */
.badge .spinner-inline{
  display: none;
  width: 8px; height: 8px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  vertical-align: middle;
  margin-left: 4px;
}
.trow[data-running="true"] .badge .spinner-inline{ display: inline-block; }
.dep-node[data-running="true"] .node-spinner{
  display:inline-block; position:absolute; top:4px; right:4px;
}
/* monitor-perf (2026-04-24): pulse 키프레임을 box-shadow(paint 강제)에서
   opacity(합성 전용)로 교체 — box-shadow 애니메이션은 매 프레임 re-paint를 유발해
   GPU 20~30% 단독 점유. opacity는 합성 레이어 투명도만 조정하므로 paint 없음. */
@keyframes pulse{
  0%,100% { opacity: 1; }
  50%     { opacity: 0.45; }
}

.btn{
  display:inline-flex; align-items:center; gap: 8px;
  height: 28px; padding: 0 10px;
  background: var(--bg-2); border: 1px solid var(--line-2);
  color: var(--ink-2);
  border-radius: var(--radius);
  font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
  font-weight: 600;
  transition: background .15s, border-color .15s, color .15s;
}
.btn:hover{ background: var(--bg-3); border-color: var(--line-hi); color: var(--ink); }
.btn[aria-pressed="true"]{
  background: rgba(200,155,106,0.08);
  border-color: var(--accent-dim);
  color: var(--accent-hi);
}
.btn .led{
  width:6px; height:6px; border-radius:50%;
  background: var(--ink-4);
  box-shadow: none;
}
.btn[aria-pressed="true"] .led{
  background: var(--accent-hi);
  box-shadow: 0 0 6px var(--accent);
  animation: led-blink 2s ease-in-out infinite;
}
@keyframes led-blink{
  0%,100%{ opacity: 1; }
  50%{ opacity:.55; }
}

.kbd{
  display:inline-block; padding: 1px 5px;
  font-family: var(--mono); font-size: 10px;
  background: var(--bg-3); border:1px solid var(--line-2);
  border-bottom-width: 2px;
  color: var(--ink-2);
  border-radius: 3px;
  vertical-align: middle;
}

/* ---------- Section chrome ---------- */
.section-head{
  display:flex; align-items: baseline; justify-content: space-between;
  gap: 12px;
  padding: 22px 0 10px;
}
.section-head .eyebrow{
  font-size: 10px; letter-spacing: .18em; text-transform: uppercase;
  color: var(--ink-4);
}
.section-head h2{
  margin: 0;
  font-family: var(--display);
  font-size: var(--font-h2); font-weight: 600;
  color: var(--ink);
}
.section-head h2::before{
  content:"\\258D"; color: var(--accent); margin-right: 6px; opacity:.8;
}
.section-head .aside{ color: var(--ink-3); font-size: 11px; display:flex; gap:12px; align-items:center;}
.section-head .ct{ color: var(--ink-3); font-size: 11px; }

/* ---------- 2. KPI Strip ---------- */
.kpi-strip{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-top: 16px;
}
.kpi{
  background: var(--bg-1);
  padding: 14px 18px 12px;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto auto;
  gap: 2px 10px;
  position: relative;
  overflow: hidden;
}
.kpi .label{
  grid-column: 1 / -1;
  font-size: 10px; letter-spacing: .2em; text-transform: uppercase;
  color: var(--ink-3); font-weight: 600;
  display:flex; align-items:center; gap: 8px;
}
.kpi .label .sw{ width: 8px; height: 8px; border-radius: 2px; }
.kpi--run   .label .sw{ background: var(--run);    box-shadow: 0 0 6px var(--run-glow); }
.kpi--fail  .label .sw{ background: var(--fail);   box-shadow: 0 0 6px var(--fail-glow); }
.kpi--bypass .label .sw{ background: var(--bypass); box-shadow: 0 0 6px var(--bypass-glow); }
.kpi--done  .label .sw{ background: var(--done);   box-shadow: 0 0 6px var(--done-glow); }
.kpi--pend  .label .sw{ background: var(--pending); box-shadow: 0 0 6px var(--pending-glow); }
.kpi .num{
  font-family: var(--mono);
  font-size: 38px; font-weight: 600; line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ink);
  align-self: end;
}
.kpi .spark{ grid-column: 1 / -1; height: 28px; margin-top: 6px; }
.kpi--run  .num{ color: var(--run); }
.kpi--fail .num{ color: var(--fail); }
.kpi--bypass .num{ color: var(--bypass); }
.kpi--done .num{ color: var(--done); }
.kpi--pend .num{ color: var(--pending); }

/* ---------- 3. Filter chips ---------- */
.chips{
  display:flex; gap: 8px;
  padding: 14px 0 6px;
  flex-wrap: wrap;
}
.chip{
  display:inline-flex; align-items:center; gap:8px;
  height: 28px; padding: 0 12px;
  background: transparent; border: 1px solid var(--line-2);
  color: var(--ink-2);
  border-radius: 999px;
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.chip:hover{ color: var(--ink); border-color: var(--line-hi); }
.chip .sw{ width:8px; height:8px; border-radius:50%; background: var(--ink-4); }
.chip[data-filter="running"] .sw{ background: var(--run); }
.chip[data-filter="failed"]  .sw{ background: var(--fail); }
.chip[data-filter="bypass"]  .sw{ background: var(--bypass); }
.chip .ct{
  color: var(--ink-4); font-size: 10px; margin-left: 2px;
  background: var(--bg-2); border: 1px solid var(--line-2);
  padding: 0 6px; height: 16px; border-radius: 999px;
  display:inline-flex; align-items:center;
}
.chip[aria-pressed="true"]{
  background: var(--bg-2);
  border-color: var(--line-hi);
  color: var(--ink);
  box-shadow: inset 0 0 0 1px var(--line-hi);
}
.chip[aria-pressed="true"][data-filter="running"]{ border-color: var(--run); color: var(--run); box-shadow: inset 0 0 0 1px rgba(74,163,255,.3), 0 0 0 3px var(--run-glow); }
.chip[aria-pressed="true"][data-filter="failed"]{  border-color: var(--fail); color: var(--fail); box-shadow: inset 0 0 0 1px rgba(255,93,93,.3), 0 0 0 3px var(--fail-glow); }
.chip[aria-pressed="true"][data-filter="bypass"]{  border-color: var(--bypass); color: var(--bypass); box-shadow: inset 0 0 0 1px rgba(209,107,224,.3), 0 0 0 3px var(--bypass-glow); }

/* ---------- main 2-col grid ---------- */
.grid{
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: 28px;
  padding-top: 8px;
}
.col{ min-width: 0; display:flex; flex-direction:column; gap: 0; }

/* ---------- 4. WP Cards ---------- */
.wp-stack{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 14px;
  align-items: start;
}
.wp{
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color .2s;
}
.wp:hover{ border-color: var(--line-2); }
.wp-head{
  display: grid;
  grid-template-columns: 72px 1fr auto;
  gap: 16px;
  padding: 16px 18px 14px;
  align-items: start;
}
.wp-donut{ position:relative; width: 72px; height: 72px; }
.wp-donut svg{ width:100%; height:100%; transform: rotate(-90deg); }
.wp-donut .pct{
  position:absolute; inset:0;
  display:grid; place-items:center;
  font-family: var(--mono);
  font-size: var(--font-pct); font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.02em;
}
.wp-donut .pct small{
  font-size: 9px; color: var(--ink-4); font-weight: 400; display:block;
  margin-top: -1px; letter-spacing: .12em;
}

.wp-title{
  min-width: 0;
  display:flex; flex-direction:column; gap: 8px;
}
.wp-title .row1{
  display:flex; align-items: baseline; gap: 10px; min-width:0;
}
.wp-title .id{
  font-family: var(--mono);
  font-size: 11px; font-weight: 600;
  color: var(--accent);
  background: rgba(200,155,106,0.08);
  border: 1px solid var(--accent-dim);
  padding: 2px 7px; border-radius: 3px;
  letter-spacing: .04em;
  white-space: nowrap;
}
.wp-title h3{
  margin: 0; font-weight: 500; font-size: var(--font-h2);
  color: var(--ink);
  font-family: var(--display);
  letter-spacing: -0.005em;
  white-space: nowrap; overflow:hidden; text-overflow: ellipsis;
  min-width: 0;
}
.wp-title .bar{
  height: 4px; width: 100%;
  background: var(--bg-3);
  border-radius: 999px;
  overflow: hidden;
  display:flex;
}
.wp-title .bar > *{ height:100%; }
.wp-title .bar .b-done{ background: var(--done); }
.wp-title .bar .b-run { background: var(--run); }
.wp-title .bar .b-fail{ background: var(--fail); }
.wp-title .bar .b-byp { background: var(--bypass); }
.wp-title .bar .b-pnd { background: var(--pending); }

.wp-counts{
  display:flex; gap: 16px;
  color: var(--ink-3);
  font-size: 11px;
  flex-wrap: wrap;
}
.wp-counts .c{ display:inline-flex; align-items:center; gap:6px; white-space: nowrap; }
.wp-counts .c .sw{ width: 7px; height: 7px; border-radius: 50%; background: var(--ink-4); }
.wp-counts .c[data-k="done"] .sw  { background: var(--done); }
.wp-counts .c[data-k="run"]  .sw  { background: var(--run); }
.wp-counts .c[data-k="fail"] .sw  { background: var(--fail); }
.wp-counts .c[data-k="byp"]  .sw  { background: var(--bypass); }
.wp-counts .c[data-k="pnd"]  .sw  { background: var(--pending); }
.wp-counts .c b{ color: var(--ink); font-weight: 600; }

.wp-meta{
  text-align: right;
  font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
  color: var(--ink-4);
  white-space: nowrap;
}
.wp-meta .big{ color: var(--ink-2); font-size: 11px; display:block; margin-bottom: 2px; letter-spacing: 0; }

.wp-tasks{ border-top: 1px solid var(--line); background: rgba(0,0,0,0.15); }
.wp-tasks > summary{
  padding: 10px 18px;
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--ink-3);
  display:flex; align-items:center; gap: 8px;
  user-select: none;
}
.wp-tasks > summary:hover{ color: var(--ink); }
.wp-tasks > summary::before{
  content: "\\25B8"; color: var(--ink-4); transition: transform .2s;
  display:inline-block;
  width: 10px;
}
.wp-tasks[open] > summary::before{ transform: rotate(90deg); color: var(--accent); }
.wp-tasks > summary .ct{ color: var(--ink-4); }
.task-list{ border-top: 1px solid var(--line); }

/* ---------- Task row ---------- */
.trow{
  display: grid;
  grid-template-columns: 4px 92px 74px 1fr auto auto auto;
  align-items: center;
  gap: 12px;
  padding: 8px 18px 8px 0;
  border-bottom: 1px solid var(--line);
  position: relative;
  transition: background .12s;
  min-height: 38px;
}
.trow:last-child{ border-bottom: 0; }
.trow:hover{ background: rgba(255,255,255,0.02); }

.trow .statusbar{
  align-self: stretch;
  width: 4px;
  background: var(--ink-4);
}
.trow[data-status="done"]    .statusbar{ background: var(--done); }
.trow[data-status="running"] .statusbar{ background: var(--run); box-shadow: 0 0 8px var(--run-glow); }
.trow[data-status="failed"]  .statusbar{ background: var(--fail); }
.trow[data-status="bypass"]  .statusbar{ background: var(--bypass); }
.trow[data-status="pending"] .statusbar{ background: var(--pending); }

.trow .tid{
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-2);
  white-space: nowrap;
}
.trow .badge{
  display:inline-flex; align-items:center; gap:5px;
  height: 20px; padding: 0 7px;
  border-radius: 3px;
  font-size: 10px; font-weight: 600;
  letter-spacing: .1em; text-transform: uppercase;
  background: var(--bg-2); color: var(--ink-3);
  border: 1px solid var(--line-2);
  justify-self: start;
}
.trow .badge::before{
  content:""; width:6px; height:6px; border-radius:50%;
  background: var(--ink-4);
}
.trow[data-status="done"] .badge{ color: var(--done); border-color: rgba(78,208,138,.25); background: rgba(78,208,138,.06); }
.trow[data-status="done"] .badge::before{ background: var(--done); }
.trow[data-status="running"] .badge{ color: var(--run); border-color: rgba(74,163,255,.25); background: rgba(74,163,255,.06); }
.trow[data-status="running"] .badge::before{ background: var(--run); animation: breathe 1.4s ease-in-out infinite; }
.trow[data-status="failed"] .badge{ color: var(--fail); border-color: rgba(255,93,93,.25); background: rgba(255,93,93,.06); }
.trow[data-status="failed"] .badge::before{ background: var(--fail); }
.trow[data-status="bypass"] .badge{ color: var(--bypass); border-color: rgba(209,107,224,.25); background: rgba(209,107,224,.06); }
.trow[data-status="bypass"] .badge::before{ background: var(--bypass); }
.trow[data-status="pending"] .badge{ color: var(--pending); border-color: rgba(240,194,74,.2); background: rgba(240,194,74,.04); }
.trow[data-status="pending"] .badge::before{ background: var(--pending); }
@keyframes breathe{ 0%,100%{ opacity:1; transform: scale(1);} 50%{ opacity: .55; transform: scale(.85);} }

/* TSK-04-01 (FR-06): phase badge colors driven by data-phase attribute on .badge */
.badge[data-phase="dd"]{
  color: var(--phase-dd);
  border-color: color-mix(in srgb, var(--phase-dd) 35%, transparent);
  background: color-mix(in srgb, var(--phase-dd) 15%, transparent);
}
.badge[data-phase="im"]{
  color: var(--phase-im);
  border-color: color-mix(in srgb, var(--phase-im) 35%, transparent);
  background: color-mix(in srgb, var(--phase-im) 15%, transparent);
}
.badge[data-phase="ts"]{
  color: var(--phase-ts);
  border-color: color-mix(in srgb, var(--phase-ts) 35%, transparent);
  background: color-mix(in srgb, var(--phase-ts) 15%, transparent);
}
.badge[data-phase="xx"]{
  color: var(--phase-xx);
  border-color: color-mix(in srgb, var(--phase-xx) 35%, transparent);
  background: color-mix(in srgb, var(--phase-xx) 15%, transparent);
}
.badge[data-phase="failed"]{
  color: var(--phase-failed);
  border-color: color-mix(in srgb, var(--phase-failed) 35%, transparent);
  background: color-mix(in srgb, var(--phase-failed) 15%, transparent);
}
.badge[data-phase="bypass"]{
  color: var(--phase-bypass);
  border-color: color-mix(in srgb, var(--phase-bypass) 35%, transparent);
  background: color-mix(in srgb, var(--phase-bypass) 15%, transparent);
}
.badge[data-phase="pending"]{
  color: var(--phase-pending);
  border-color: color-mix(in srgb, var(--phase-pending) 35%, transparent);
  background: color-mix(in srgb, var(--phase-pending) 10%, transparent);
}

.trow .ttitle{
  color: var(--ink);
  font-family: var(--sans);
  font-size: var(--font-body);
  white-space: nowrap; overflow:hidden; text-overflow: ellipsis;
  min-width: 0;
}
.trow .ttitle .path{ color: var(--ink-4); font-family: var(--mono); font-size: 11px; margin-right: 6px;}

.trow .elapsed{ color: var(--ink-3); font-size: 11px; white-space: nowrap; }
.trow .retry{ color: var(--ink-4); font-size: 11px; white-space: nowrap; }
.trow .retry.hot{ color: var(--pending); }
.trow .flags{ display:flex; gap: 4px; padding-right: 4px; }
.trow .flag{
  font-size: 10px; font-weight: 600;
  padding: 1px 5px; border-radius: 2px;
  background: var(--bg-3); color: var(--ink-3);
  border: 1px solid var(--line-2);
}
.trow .flag.f-crit{ color: var(--fail); border-color: rgba(255,93,93,.3); background: rgba(255,93,93,.05); }
.trow .flag.f-new { color: var(--accent); border-color: var(--accent-dim); background: rgba(200,155,106,.06); }

/* filter hide */
body[data-filter="running"] .trow:not([data-status="running"]),
body[data-filter="failed"]  .trow:not([data-status="failed"]),
body[data-filter="bypass"]  .trow:not([data-status="bypass"]) { display: none; }

/* legacy badge classes for non-.trow contexts */
.badge-dd { background: rgba(56,139,253,0.15); color: #4aa3ff; border: 1px solid #4aa3ff; }
.badge-im { background: rgba(188,140,255,0.15); color: #bc8cff; border: 1px solid #bc8cff; }
.badge-ts { background: rgba(63,185,80,0.15); color: var(--done); border: 1px solid var(--done); }
.badge-xx { background: rgba(139,148,158,0.15); color: var(--ink-3); border: 1px solid var(--ink-3); }
.badge-run { background: rgba(74,163,255,0.15); color: var(--run); border: 1px solid var(--run); animation: pulse 1.5s ease-in-out infinite; }
.badge-fail { background: rgba(255,93,93,0.15); color: var(--fail); border: 1px solid var(--fail); }
.badge-bypass { background: rgba(209,107,224,0.15); color: var(--bypass); border: 1px solid var(--bypass); }
.badge-pending { background: rgba(110,118,129,0.15); color: var(--ink-3); border: 1px solid var(--ink-3); }
.badge-warn { background: rgba(255,93,93,0.2); color: var(--fail); border: 1px solid var(--fail); }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 10px; font-size: 0.78rem; font-weight: 600; }

/* ---------- 5. Features ---------- */
.features-wrap{ border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--bg-1); overflow:hidden;}

/* ---------- 6. Live Activity ---------- */
.panel{
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--bg-1);
  overflow: hidden;
}
.activity{ max-height: 420px; overflow-y: auto; padding: 4px 0; }

/* ---------- 8. Team Agents ---------- */
.team{ padding: 0; }
.pane{ border-bottom: 1px solid var(--line); }
.pane:last-child{ border-bottom: 0; }
.pane-head{
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 10px; align-items: center;
  padding: 20px 14px 16px;
}
.pane-head .name{
  font-family: var(--mono);
  font-size: 12px; font-weight: 600;
  color: var(--ink);
  display:inline-flex; align-items:center; gap: 6px;
}
.pane-head .name::before{
  content: "\\25CF"; color: var(--done); font-size: 10px;
}
.pane[data-state="idle"] .pane-head .name::before{ color: var(--ink-4); }
.pane-head .meta{ color: var(--ink-3); font-size: 11px; white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }
.pane-head .cmd{
  color: var(--ink-2); font-family: var(--mono); font-size: 11px;
  background: var(--bg-2); border: 1px solid var(--line-2);
  padding: 1px 6px; border-radius: 3px;
}
.mini-btn{
  display:inline-flex; align-items:center; gap:5px;
  height: 22px; padding: 0 8px;
  font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
  font-weight: 600;
  background: transparent; border: 1px solid var(--line-2);
  color: var(--ink-3); border-radius: 3px;
  transition: all .12s;
}
.mini-btn:hover{ background: var(--bg-2); color: var(--ink); border-color: var(--line-hi); }
.mini-btn.primary{ border-color: var(--accent-dim); color: var(--accent-hi); }
.mini-btn.primary:hover{ background: rgba(200,155,106,.08); }

.pane-preview{
  margin: 0 14px 12px;
  padding: 8px 10px;
  background: #07090c;
  border: 1px solid var(--line); border-radius: var(--radius);
  font-family: var(--mono); font-size: 11px; line-height: 1.5;
  color: var(--ink-2); white-space: pre-wrap; overflow-x: auto;
  overflow-y: auto;
  position: relative;
  max-height: 9em;
}
.pane-preview.empty{ color: var(--ink-3); }
.pane-preview::before{
  content: "\\25B8 last 6 lines"; position: absolute; top: -8px; left: 10px;
  font-size: 9px; letter-spacing: .1em; text-transform: uppercase;
  background: var(--bg-1); padding: 0 5px;
  color: var(--ink-4);
}
[lang="ko"] .pane-preview::before{ content: "\\25B8 최근 6줄"; }
.pane-preview .prompt{ color: var(--done); }
.pane-preview .dim{ color: var(--ink-4); }
.pane-preview .err{ color: var(--fail); }
.pane-preview .warn{ color: var(--pending); }
.pane-preview .info{ color: var(--run); }

/* ---------- 9. Subagents ---------- */
.subs{
  padding: 12px 14px;
  display:flex; flex-wrap: wrap; gap: 8px;
}
.sub{
  display:inline-flex; align-items:center; gap: 8px;
  padding: 4px 10px 4px 8px;
  background: var(--bg-2); border: 1px solid var(--line-2);
  border-radius: 999px; font-size: 11px; color: var(--ink-2);
  font-family: var(--mono);
}
.sub .sw{ width: 7px; height: 7px; border-radius: 50%; background: var(--ink-4); }
.sub[data-state="running"] .sw{ background: var(--run); box-shadow: 0 0 6px var(--run-glow); animation: breathe 1.4s infinite;}
.sub[data-state="done"] .sw{ background: var(--done); }
.sub[data-state="failed"] .sw{ background: var(--fail); }
.sub .n{ color: var(--ink-4); font-size: 10px;}

/* ---------- 10. Phase history ---------- */
/* monitor-perf (2026-04-24): content-visibility:auto 로 뷰포트 밖 렌더·페인트 스킵.
   phase history는 길 수 있고 사용자가 스크롤해야 보이므로 뷰포트 밖 비용 0으로 낮춤.
   contain-intrinsic-size 는 placeholder 크기 — 스크롤바 뜀 방지. */
.history{
  margin-top: 28px; border: 1px solid var(--line);
  border-radius: var(--radius-lg); background: var(--bg-1); overflow: hidden;
  content-visibility: auto;
  contain-intrinsic-size: 1px 640px;
}
/* WP/live-activity/dep-graph도 뷰포트 밖이면 렌더 스킵 (데이터 교체되면 auto-invalidate) */
[data-section="wp-cards"],
[data-section="live-activity"],
[data-section="dep-graph"]{
  content-visibility: auto;
  contain-intrinsic-size: 1px 720px;
}
.history table{ width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 11.5px; }
.history th, .history td{
  padding: 8px 14px; text-align: left;
  border-bottom: 1px solid var(--line); white-space: nowrap; color: var(--ink-2);
}
.history tbody tr:last-child td{ border-bottom: 0; }
.history tbody tr:hover{ background: rgba(255,255,255,.02);}
.history th{ font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-4); font-weight: 600; background: var(--bg-2); }
.history td.idx{ color: var(--ink-4); width: 36px; text-align: right; }
.history td.t{ color: var(--ink-3); }
.history td.tid{ color: var(--ink); font-weight: 600;}
.history td.ev{ color: var(--ink-3);}
.history td .arr{ color: var(--ink-4); margin: 0 4px;}
.history td .to.done{ color: var(--done); font-weight: 600;}
.history td .to.running{ color: var(--run); font-weight: 600;}
.history td .to.failed{ color: var(--fail); font-weight: 600;}
.history td .to.bypass{ color: var(--bypass); font-weight: 600;}
.history td.el{ color: var(--ink-4); }

/* ---------- 11. Drawer ---------- */
.drawer-backdrop{
  position: fixed; inset: 0;
  /* monitor-perf: 블러 합성 제거 — drawer 닫혀도 Chrome이 pre-compute하여 GPU 상시 점유.
     배경을 더 어둡게(0.55→0.70) 하여 blur 없이도 초점 분리 유지. */
  background: rgba(0,0,0,0.70);
  z-index: 80;
  opacity: 0; pointer-events: none;
  transition: opacity .2s;
}
.drawer-backdrop[aria-hidden="false"]{ opacity:1; pointer-events: auto; }

.drawer{
  position: fixed; top: 0; right: 0; bottom: 0;
  width: 640px; max-width: 100vw;
  background: var(--bg-1);
  border-left: 1px solid var(--line-2);
  z-index: 90;
  transform: translateX(100%);
  transition: transform .24s cubic-bezier(.3,.7,.2,1);
  display: flex; flex-direction: column;
}
.drawer[aria-hidden="false"]{ transform: translateX(0); }
.drawer-head{
  display: grid; grid-template-columns: 1fr auto;
  align-items: start; gap: 14px;
  padding: 18px 22px 14px; border-bottom: 1px solid var(--line);
}
.drawer-head h3{
  margin: 0; font-family: var(--display); font-size: 16px; font-weight: 600; color: var(--ink);
  display:flex; align-items:center; gap: 8px;
}
.drawer-head h3::before{
  content:""; width: 8px; height: 8px; border-radius: 50%;
  background: var(--done); box-shadow: 0 0 6px var(--done-glow);
}
.drawer-head .meta{ color: var(--ink-3); font-size: 11px; margin-top: 4px; font-family: var(--mono); display:flex; gap: 14px; flex-wrap: wrap; }
.drawer-head .meta b{ color: var(--ink-2); font-weight: 500; }
.drawer-close{
  width: 30px; height: 30px; border:1px solid var(--line-2);
  border-radius: 4px; display:grid; place-items:center; color: var(--ink-3);
  transition: all .12s;
}
.drawer-close:hover{ color: var(--fail); border-color: var(--fail); background: rgba(255,93,93,.06); }

.drawer-status{
  display:flex; align-items:center; gap: 10px;
  padding: 10px 22px;
  font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ink-4); border-bottom: 1px solid var(--line); background: var(--bg);
}
.drawer-status .poll{ color: var(--done); display:inline-flex; align-items:center; gap: 6px;}
.drawer-status .poll::before{
  content:""; width: 6px; height: 6px; border-radius: 50%; background: var(--done);
  animation: pulse 1.6s infinite;
}

.drawer-pre{
  flex: 1; overflow: auto; margin: 0; padding: 16px 22px 22px;
  font-family: var(--mono); font-size: 12px; line-height: 1.55;
  color: var(--ink-2); background: #07090c; white-space: pre;
}
.drawer-pre .prompt{ color: var(--done); }
.drawer-pre .dim{ color: var(--ink-4); }
.drawer-pre .err{ color: var(--fail); }
.drawer-pre .warn{ color: var(--pending); }
.drawer-pre .info{ color: var(--run); }
.drawer-pre .hi{ color: var(--accent); }

/* legacy compatibility — empty-state helpers used by _empty_section */
.info { color: var(--ink-3); font-size: 0.9rem; }
.empty { color: var(--ink-3); font-style: italic; }
/* sticky-hdr: used by _section_sticky_header (backward-compat) */
.sticky-hdr {
  position: sticky; top: 0; z-index: 20;
  background: var(--bg); border-bottom: 1px solid var(--line);
  padding: 0.75rem 1.5rem 0.5rem;
}
.logo-dot { color: var(--done); font-size: 1.2rem; }
.hdr-title { font-weight: 700; font-size: 1rem; }
.hdr-project { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink-3); font-size: 0.9rem; max-width: 30ch; }
.hdr-refresh { font-family: var(--mono); color: var(--ink-3); font-size: 0.85rem; }
/* kpi legacy — v3 redesign replaced with .kpi/.kpi--{state}/.kpi .label/.kpi .num/.kpi .spark;
   selectors below are kept for backward-compat CSS assertion tests only */
.kpi-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.5rem; }
.kpi-card { background: var(--bg-1); border: 1px solid var(--line); border-radius: 6px; padding: 0.5rem 0.75rem; min-width: 7rem; font-size: 0.85rem; }
.kpi-card.running { border-left: 4px solid var(--run); }
.kpi-card.failed  { border-left: 4px solid var(--fail); }
.kpi-card.bypass  { border-left: 4px solid var(--bypass); }
.kpi-card.done    { border-left: 4px solid var(--done); }
.kpi-card.pending { border-left: 4px solid var(--pending); }
.kpi-label { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em; color: var(--ink-3); text-transform: uppercase; display: block; }
.kpi-num { font-size: 1.8rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; display: block; }
.kpi-sparkline { display: block; width: 100%; height: 24px; margin-top: 0.25rem; }
.kpi-section { padding: 0.75rem 0; margin-bottom: 0.5rem; }

/* ---------- subproject tabs (TSK-01-02) ---------- */
.subproject-tabs{
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0.5rem 0 0;
  margin: 0 0 0.5rem;
  border-bottom: 1px solid var(--line);
  font-size: var(--font-body);
  font-family: var(--sans);
}
.subproject-tabs a{
  color: var(--ink-2);
  text-decoration: none;
  padding: 0.4rem 0.8rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}
.subproject-tabs a:hover{
  color: var(--ink);
}
.subproject-tabs a.active,
.subproject-tabs a[aria-current="page"]{
  color: var(--accent-hi);
  border-bottom: 2px solid var(--accent);
  font-weight: 600;
}

/* ---------- lang-toggle active ---------- */
.cmdbar .lang-toggle a.active,
.cmdbar .lang-toggle a[aria-current="page"] {
  color: var(--accent-hi);
  border-color: var(--accent-dim);
  background: rgba(200,155,106,0.08);
}

/* ---------- sparkline (redesign) ---------- */
.spark {
  grid-column: 1 / -1;
  height: 28px;
  margin-top: 6px;
  display: block;
  width: 100%;
}

/* ---------- 6. Activity row ---------- */
.arow {
  display: grid;
  grid-template-columns: 52px 88px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 5px 12px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  animation: fade-in .4s ease-out;
}
.arow:hover{ background: rgba(255,255,255,.02); }
.arow .t { color: var(--ink-4); font-family: var(--mono); white-space: nowrap; }
.arow .tid { color: var(--accent); font-family: var(--mono); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.arow .evt { color: var(--ink-2); display:flex; align-items:center; gap:4px; min-width:0; overflow:hidden; }
.arow .evt .arrow { color: var(--ink-4); }
.arow .evt .from { color: var(--ink-3); }
.arow .evt .to { font-weight: 600; color: var(--ink-2); }
.arow[data-to="done"]    .to{ color: var(--done); }
.arow[data-to="running"] .to{ color: var(--run); }
.arow[data-to="failed"]  .to{ color: var(--fail); }
.arow[data-to="bypass"]  .to{ color: var(--bypass); }
.arow[data-to="pending"] .to{ color: var(--pending); }
.arow .el { color: var(--ink-4); font-size: 11px; text-align: right; white-space: nowrap; }
.arow .log { grid-column: 1 / -1; font-size: 10px; color: var(--ink-4); font-family: var(--mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-top: 2px; border-top: 1px solid rgba(255,255,255,.04); }
@keyframes fade-in{from{opacity:0; transform:translateY(-4px);}to{opacity:1; transform:translateY(0);}}
@media (prefers-reduced-motion: reduce){ .arow{ animation: none; } }

/* ---------- dep-node HTML 레이블 (TSK-04-03) ---------- */
/* cytoscape-node-html-label 플러그인이 각 노드 위에 오버레이하는 2줄 카드 */
/* 단서 1: border-left-color (상태별 스트립)
   단서 2: .dep-node-id color override (상태별 ID 글자색)
   단서 3: --_tint color-mix() 배경 틴트 (color-mix 미지원 시 transparent fallback → 단서 1/2만 유지) */
.dep-node {
  display: flex; flex-direction: column; align-items: flex-start; justify-content: center;
  width: 180px; height: 72px; padding: 8px 12px 8px 16px; box-sizing: border-box;
  border-radius: 8px;
  border: 1px solid var(--ink-4);
  border-left: 4px solid var(--ink-4);
  background: var(--bg-2);
  background-image: linear-gradient(90deg, var(--_tint, transparent), transparent 45%);
  transition: transform .15s ease, box-shadow .15s ease;
  pointer-events: none;
  overflow: hidden;
}
.dep-node:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,.45);
}
.dep-node-id {
  font-family: var(--mono); font-size: 10px; font-weight: 700;
  color: var(--ink-3);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
}
.dep-node-title {
  font-family: var(--font-body); font-size: 12.5px; font-weight: 400;
  color: var(--ink);
  overflow: hidden; text-overflow: ellipsis; max-width: 100%;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
/* --- 상태 5종 (단서 1: 스트립, 단서 2: ID 글자색, 단서 3: 배경 틴트) --- */
.dep-node.status-done {
  border-left-color: var(--done);
  --_tint: color-mix(in srgb, var(--done) 10%, transparent);
}
.dep-node.status-done .dep-node-id { color: var(--done); }
.dep-node.status-running {
  border-left-color: var(--run);
  --_tint: color-mix(in srgb, var(--run) 10%, transparent);
}
.dep-node.status-running .dep-node-id { color: var(--run); }
.dep-node.status-pending {
  border-left-color: var(--ink-3);
  --_tint: color-mix(in srgb, var(--ink-3) 8%, transparent);
}
.dep-node.status-pending .dep-node-id { color: var(--ink-3); }
.dep-node.status-failed {
  border-left-color: var(--fail);
  --_tint: color-mix(in srgb, var(--fail) 10%, transparent);
}
.dep-node.status-failed .dep-node-id { color: var(--fail); }
.dep-node.status-bypassed {
  border-left-color: #a855f7;
  --_tint: color-mix(in srgb, #a855f7 10%, transparent);
}
.dep-node.status-bypassed .dep-node-id { color: #a855f7; }
/* TSK-04-01 (FR-06): data-phase 기반 dep-node ID 글자색 — .status-* 규칙 이후에 배치하여 우선 적용 */
.dep-node[data-phase="dd"] .dep-node-id { color: var(--phase-dd); }
.dep-node[data-phase="im"] .dep-node-id { color: var(--phase-im); }
.dep-node[data-phase="ts"] .dep-node-id { color: var(--phase-ts); }
.dep-node[data-phase="xx"] .dep-node-id { color: var(--phase-xx); }
.dep-node[data-phase="failed"] .dep-node-id { color: var(--phase-failed); }
.dep-node[data-phase="bypass"] .dep-node-id { color: var(--phase-bypass); }
/* --- 모디파이어: critical (FR-05: 앰버 테두리 + 앰버 배경 틴트 + 글로우) --- */
.dep-node.critical {
  border-color: var(--critical);
  --_tint: color-mix(in srgb, var(--critical) 12%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--critical) 35%, transparent);
}
/* --- failed + critical 동시 적용 시 failed(빨강) 우선 (specificity 0,3,0 > 0,2,0) --- */
.dep-node.status-failed.critical {
  border-color: var(--fail);
  --_tint: color-mix(in srgb, var(--fail) 10%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--fail) 35%, transparent);
}
/* --- 모디파이어: bottleneck (dashed border) --- */
.dep-node.bottleneck {
  border-style: dashed;
}

/* --- legend <ul>/<li> reset (TSK-03-03) --- */
ul#dep-graph-legend { list-style: none; margin: 0; padding: 0; }

/* ---------- dep-graph summary chips (TSK-04-04) ---------- */
/* AC-32: color values match #dep-graph-legend inline style hex 1:1 */
#dep-graph-summary {
  display: flex; gap: 14px; align-items: baseline;
  font-size: 12.5px; font-variant-numeric: tabular-nums;
}
.dep-stat { display: inline-flex; gap: 5px; align-items: baseline; }
.dep-stat em { font-style: normal; font-weight: 500; opacity: .85; letter-spacing: .02em; }
.dep-stat b  { font-weight: 700; }
.dep-stat-total    em,
.dep-stat-total    b { color: var(--ink); }
.dep-stat-done     em,
.dep-stat-done     b { color: #22c55e; }
.dep-stat-running  em,
.dep-stat-running  b { color: #eab308; }
.dep-stat-pending  em,
.dep-stat-pending  b { color: #94a3b8; }
.dep-stat-failed   em,
.dep-stat-failed   b { color: #ef4444; }
.dep-stat-bypassed em,
.dep-stat-bypassed b { color: #a855f7; }
.dep-graph-summary-extra { color: var(--ink-2); margin-left: 10px; }

/* ---------- dep-graph legend + wheel-zoom toggle ---------- */
#dep-graph-legend {
  display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
  margin-top: 8px; font-size: 11px;
}
#dep-graph-legend .leg-item { font-family: var(--mono); }
#dep-graph-legend .dep-graph-wheel {
  margin-left: auto;
  display: inline-flex; gap: 6px; align-items: center;
  color: var(--ink-3); cursor: pointer; user-select: none;
  font-size: 11px; letter-spacing: .02em;
}
#dep-graph-legend .dep-graph-wheel input { margin: 0; cursor: pointer; }

/* ---------- responsive ---------- */
@media (max-width: 1280px){
  .grid{ grid-template-columns: 1fr; }
}
@media (max-width: 768px){
  .shell{ padding: 0 12px; }
  .cmdbar{ margin: 0 -12px; padding: 0 12px; grid-template-columns: 1fr auto; }
  .cmdbar .meta{ display:none; }
  .trow{ grid-template-columns: 4px auto 1fr auto; }
  .trow .badge, .trow .retry, .trow .flags{ display:none; }
  .drawer{ width: 100vw; }
}

/* ---------- TSK-04-02 FR-01: .info-btn click trigger ---------- */
.info-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:18px;
  height:18px;
  margin:0 4px;
  padding:0;
  background:transparent;
  border:1px solid var(--border);
  border-radius:50%;
  color:var(--ink-3);
  cursor:pointer;
  font:11px/1 var(--font-mono);
  user-select:none;
}
.info-btn:hover,
.info-btn:focus-visible{
  color:var(--ink);
  border-color:var(--ink-3);
  outline:none;
}
.info-btn[aria-expanded="true"]{
  color:var(--accent);
  border-color:var(--accent);
}

/* ---------- TSK-04-02 FR-01: singleton info popover ---------- */
.info-popover{
  position:absolute;
  z-index:100;
  max-width:420px;
  min-width:240px;
  background:var(--bg-2);
  border:1px solid var(--border);
  border-radius:6px;
  padding:10px 12px;
  font:12px/1.4 var(--font-mono);
  box-shadow:0 8px 24px rgba(0,0,0,0.18);
}
.info-popover[hidden]{ display:none; }
.info-popover dl{ margin:0; }
.info-popover dt{ color:var(--ink-3); font-size:10px; margin-top:6px; }
.info-popover dd{ margin:0; color:var(--ink); }
.info-popover dl.phase-models dt{ color:var(--ink-3); font-size:10px; margin-top:4px; }
.info-popover dl.phase-models dd{ margin:0; color:var(--ink); font-size:11px; }
/* tail triangle — default placement above row (tail points down) */
.info-popover::before{
  content:"";
  position:absolute;
  left:16px;
  bottom:-6px;
  width:0;
  height:0;
  border-left:6px solid transparent;
  border-right:6px solid transparent;
  border-top:6px solid var(--border);
}
.info-popover::after{
  content:"";
  position:absolute;
  left:17px;
  bottom:-5px;
  width:0;
  height:0;
  border-left:5px solid transparent;
  border-right:5px solid transparent;
  border-top:5px solid var(--bg-2);
}
.info-popover[data-placement="below"]::before{
  top:-6px;
  bottom:auto;
  border-top:none;
  border-bottom:6px solid var(--border);
}
.info-popover[data-placement="below"]::after{
  top:-5px;
  bottom:auto;
  border-top:none;
  border-bottom:5px solid var(--bg-2);
}

/* ---------- TSK-02-05: model chip + escalation flag ---------- */
.model-chip{
  display:inline-block;
  padding:1px 6px;
  margin-left:6px;
  font:10px/1.4 var(--font-mono);
  border-radius:3px;
  background:var(--bg-3);
  color:var(--ink-2);
  border:1px solid var(--border);
  vertical-align:middle;
}
.model-chip[data-model="opus"]{ background:#3b2f4a; color:#e8d8ff; border-color:#6b4a8a; }
.model-chip[data-model="sonnet"]{ background:#2a3a4a; color:#cce0f0; border-color:#3a6080; }
.model-chip[data-model="haiku"]{ background:#2a3f30; color:#c8e6c9; border-color:#3a6040; }
.escalation-flag{
  margin-left:4px;
  color:var(--pending);
  font-size:11px;
  vertical-align:middle;
}
/* TSK-05-01: filter-bar — sticky top, z-index 70 (below slide-panel:90, info-popover:100) */
.filter-bar{
  position:sticky;
  top:0;
  z-index:70;
  display:flex;
  gap:8px;
  padding:8px 12px;
  background:var(--bg-1);
  border-bottom:1px solid var(--border);
  flex-wrap:wrap;
}
.filter-bar input,
.filter-bar select,
.filter-bar button{
  font:12px var(--font-body);
  padding:4px 8px;
  background:var(--bg-2);
  color:var(--ink-1);
  border:1px solid var(--border);
  border-radius:3px;
}
.filter-bar input{ min-width:140px; }
"""

def _minify_css(css: str) -> str:
    """Collapse verbose CSS into a compact single-line string for SSR tests."""
    return re.sub(r"\n\s*", " ", css).strip()


DASHBOARD_CSS = _minify_css(DASHBOARD_CSS)


# ---------------------------------------------------------------------------
# Static bundle assembly (TSK-01-02 / TSK-01-03)
# ---------------------------------------------------------------------------
# In-memory source of truth for /static/style.css and /static/app.js. Inline
# constants (``DASHBOARD_CSS``, ``_PANE_CSS``, ``_task_panel_css()``) and the
# three JS blocks (``_DASHBOARD_JS``, ``_PANE_JS``, ``_task_panel_js()``) are
# concatenated at request time and fingerprinted for ``?v=`` cache-busting.
# ``handlers._serve_local_static`` prefers this bundle over the on-disk files
# under ``monitor_server/static/`` so edits to the inline constants never drift
# from what the browser receives.

_STATIC_BUNDLE_CACHE: "dict" = {}


def get_static_bundle(name: str) -> bytes:
    """Return the current bytes for ``/static/{name}``.

    Supported names: ``style.css``, ``app.js``. Empty bytes for anything else
    (vendor JS is served separately from the plugin vendor dir).
    """
    if name == "style.css":
        body = "\n".join([
            DASHBOARD_CSS,
            _task_panel_css(),
            _PANE_CSS,
        ])
        return body.encode("utf-8")
    if name == "app.js":
        body = "\n".join([
            _DASHBOARD_JS,
            _task_panel_js(),
            _PANE_JS,
        ])
        return body.encode("utf-8")
    return b""


def get_static_version(name: str) -> str:
    """Return a stable short fingerprint for ``/static/{name}`` (md5, 8 chars).

    Cached per-name for the process lifetime — inline constants are effectively
    immutable once the module is imported.
    """
    cached = _STATIC_BUNDLE_CACHE.get(name)
    if cached is not None:
        return cached
    data = get_static_bundle(name)
    if not data:
        return ""
    fp = hashlib.md5(data).hexdigest()[:8]
    _STATIC_BUNDLE_CACHE[name] = fp
    return fp


def _esc(value) -> str:
    """Safely HTML-escape any value (coerce to str, quote=True)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _refresh_seconds(model: dict) -> int:
    raw = model.get("refresh_seconds", _DEFAULT_REFRESH_SECONDS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_REFRESH_SECONDS
    if value < 1:
        return _DEFAULT_REFRESH_SECONDS
    return value


# _signal_set: moved to monitor_server.api (C0-4).


def _format_elapsed(item, lang: str = "ko") -> str:
    """Return human-readable duration (e.g. '1h 35m' / '1시간 35분'), else ``"-"``."""
    elapsed = getattr(item, "elapsed_seconds", None)
    if elapsed is None:
        return "-"
    try:
        total = int(float(elapsed))
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if lang == "en":
        if hours:
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"
        if minutes:
            return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
        return f"{seconds}s"
    else:
        if hours:
            return f"{hours}시간 {minutes}분" if minutes else f"{hours}시간"
        if minutes:
            return f"{minutes}분 {seconds}초" if seconds else f"{minutes}분"
        return f"{seconds}초"


def _retry_count(item) -> int:
    """Count ``*.fail`` events in phase_history_tail."""
    tail = getattr(item, "phase_history_tail", None) or []
    count = 0
    for entry in tail:
        event = getattr(entry, "event", None)
        if isinstance(event, str) and event.endswith(".fail"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# DDTR phase model helpers
# ---------------------------------------------------------------------------

def _MAX_ESCALATION() -> int:
    """환경변수 MAX_ESCALATION(기본 2)을 안전하게 파싱한다.

    매 호출마다 환경변수를 재읽어 테스트의 monkeypatch.setenv 즉시 반영.
    음수/0/비숫자/빈 문자열 → 기본값 2 폴백.
    """
    raw = os.environ.get("MAX_ESCALATION", "").strip()
    try:
        val = int(raw)
        if val > 0:
            return val
    except (ValueError, TypeError):
        pass
    return 2


def _test_phase_model(item) -> str:
    """retry_count 기반으로 Test phase 모델을 결정한다 (TSK-02-05 TRD §3.10).

    규칙:
    - rc >= _MAX_ESCALATION() → 'opus'
    - rc >= 1 → 'sonnet'
    - 그 외 → 'haiku'
    """
    rc = _retry_count(item)
    if rc >= _MAX_ESCALATION():
        return "opus"
    if rc >= 1:
        return "sonnet"
    return "haiku"


def _phase_models_for(item) -> dict:
    """DDTR 4개 phase별 모델 dict 반환 (TSK-02-05 TRD §3.10).

    Keys: design, build, test, refactor.
    - design: item.model (wbs.md 필드) 또는 'sonnet' 폴백
    - build, refactor: 'sonnet' 고정
    - test: _test_phase_model(item) (retry_count 기반)
    """
    design_model = getattr(item, "model", None) or "sonnet"
    return {
        "design": design_model,
        "build": "sonnet",
        "test": _test_phase_model(item),
        "refactor": "sonnet",
    }


# DDTR phase model 람다 테이블 (TRD §3.10 — Dep-Graph 노드 향후 소비용)
_DDTR_PHASE_MODELS = {
    "dd": lambda t: getattr(t, "model", None) or "sonnet",
    "im": lambda t: "sonnet",
    "ts": _test_phase_model,
    "xx": lambda t: "sonnet",
}


def _status_badge(status: Optional[str], bypassed: bool, running: bool, failed: bool) -> str:
    """Render a status badge span with priority: bypass > failed > running > status."""
    if bypassed:
        emoji, label, css = "🟡", "BYPASSED", "badge-bypass"
    elif failed:
        emoji, label, css = "🔴", "FAILED", "badge-fail"
    elif running:
        emoji, label, css = "🟠", "RUNNING", "badge-run"
    else:
        emoji, label, css = _STATUS_BADGE_MAP.get(status or "", _STATUS_BADGE_DEFAULT)
    return f'<span class="badge {css}">{emoji} {_esc(label)}</span>'


def _group_preserving_order(
    items: Iterable,
    key: Callable[[Any], str],
) -> Tuple[Dict[str, list], List[str]]:
    """Group ``items`` by ``key(item)``, preserving first-seen order.

    Returns ``(groups, order)`` — ``groups[k]`` is the list of items with that
    key, and ``order`` is the keys in first-seen order. Callers that previously
    duplicated this bookkeeping (``_section_wbs``, ``_section_team``,
    ``_section_subagents``) share the same implementation here.
    """
    groups: Dict[str, list] = {}
    order: List[str] = []
    for item in items:
        k = key(item)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(item)
    return groups, order


# v3 per-section eyebrow + aside metadata. Keys match section anchors.
_SECTION_EYEBROWS = {
    "wp-cards":   ("planning",    ""),
    "features":   ("unassigned",  ""),
    "activity":   ("stream",      'last 20 events · <b style="color:var(--done)">tailing</b>'),
    "team":       ("tmux",        ""),
    "subagents":  ("agent-pool",  "fan-out / fan-in signals"),
    "phases":     ("audit",       "last 10 transitions"),
}

_SECTION_DEFAULT_HEADINGS = {
    "wp-cards": "Work Packages",
    "features": "Features",
    "activity": "Live Activity",
    "team": "Team Agents (tmux)",
    "subagents": "Subagents (agent-pool)",
}


def _resolve_heading(anchor: str, heading: "Optional[str]") -> str:
    """Return explicit *heading* or the legacy default heading for *anchor*."""
    return heading if heading is not None else _SECTION_DEFAULT_HEADINGS.get(anchor, "")


def _section_wrap(anchor: str, heading: str, body: str) -> str:
    """Render a v3 ``<section>`` block with ``.section-head`` (eyebrow + h2 + aside).

    The eyebrow/aside pair is looked up from ``_SECTION_EYEBROWS`` by anchor; unknown
    anchors fall back to an empty eyebrow (no eyebrow shown). ``id`` is preserved
    for backward-compat with in-page anchors (``/#wbs`` etc.).
    """
    eyebrow, aside = _SECTION_EYEBROWS.get(anchor, ("", ""))
    eyebrow_html = f'<div class="eyebrow">{eyebrow}</div>\n      ' if eyebrow else ""
    aside_html = f'\n    <div class="aside">{aside}</div>' if aside else ""
    return (
        f'<section id="{anchor}">\n'
        '  <div class="section-head">\n'
        f'    <div>{eyebrow_html}<h2>{heading}</h2></div>{aside_html}\n'
        '  </div>\n'
        f'{body}\n'
        '</section>'
    )


def _empty_section(anchor: str, heading: str, message: str, css: str = "empty") -> str:
    """Render a standard empty-state section (``.empty`` or ``.info`` variant)."""
    return _section_wrap(anchor, heading, f'  <p class="{css}">{message}</p>')


def _section_header(model: dict, lang: str = "ko", subproject: str = "") -> str:
    """v3 cmdbar header: brand + meta + lang-toggle + actions.

    TSK-02-02: ``lang`` / ``subproject`` 파라미터 추가.  헤더 우측
    actions 블록 안에 ``<nav class="lang-toggle">`` 를 삽입하여 ko/en
    전환 링크를 렌더링한다.  subproject 쿼리가 있으면 lang 링크에 보존한다.
    """
    generated_at = _esc(model.get("generated_at", ""))
    project_root = _esc(model.get("project_root", ""))
    docs_dir = _esc(model.get("docs_dir", ""))
    refresh_s = _refresh_seconds(model)

    # Build lang-toggle href pairs (subproject preserved when non-empty).
    if subproject:
        sp_enc = quote(subproject, safe="")
        href_ko = f"?lang=ko&subproject={sp_enc}"
        href_en = f"?lang=en&subproject={sp_enc}"
    else:
        href_ko = "?lang=ko"
        href_en = "?lang=en"

    ko_current = ' aria-current="page" class="active"' if lang == "ko" else ""
    en_current = ' aria-current="page" class="active"' if lang == "en" else ""
    lang_toggle_html = (
        f'<nav class="lang-toggle">'
        f'<a href="{href_ko}"{ko_current}>한</a>'
        f' <a href="{href_en}"{en_current}>EN</a>'
        f'</nav>\n'
    )
    top_nav_html = (
        '<nav class="top-nav">'
        '<a href="#wp-cards">Wp-Cards</a>'
        '<a href="#features">Features</a>'
        '<a href="#team">Team</a>'
        '<a href="#subagents">Subagents</a>'
        '<a href="#activity">Activity</a>'
        '<a href="#phases">Phases</a>'
        '</nav>\n'
    )

    return (
        '<header class="cmdbar" data-section="hdr" role="banner" aria-label="Command bar">\n'
        '  <div class="brand">\n'
        '    <span class="logo" aria-hidden="true">\n'
        '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round">\n'
        '        <path d="M4 7 L10 12 L4 17"/>\n'
        '        <path d="M13 17 L20 17"/>\n'
        '      </svg>\n'
        '    </span>\n'
        '    <span class="title">dev-plugin</span>\n'
        '    <span class="slash">/</span>\n'
        '    <span class="sub">monitor</span>\n'
        '  </div>\n'
        '  <div class="meta" role="group" aria-label="Session info">\n'
        f'    <span><span class="k">project</span>'
        f'<span class="v path">{project_root}</span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">docs</span><span class="v">{docs_dir}</span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">now</span>'
        # monitor-perf (2026-04-24): 서버에서 now를 박으면 매 응답마다 HTML이 달라져 ETag/304 불가.
        # 클라이언트 startClock()이 매초 갱신하므로 초기값을 빈 문자열로 두어도 UX 영향 없음.
        f'<span class="v" id="clock"></span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">interval</span>'
        f'<span class="v">{refresh_s}s</span></span>\n'
        '  </div>\n'
        '  <div class="actions">\n'
        f'    {lang_toggle_html}'
        f'    {top_nav_html}'
        '    <span class="pulse" aria-live="polite">'
        '<span class="dot" aria-hidden="true"></span> live</span>\n'
        '    <button class="btn refresh-toggle" type="button"'
        ' aria-pressed="true" aria-label="Auto-refresh">\n'
        '      <span class="led" aria-hidden="true"></span>\n'
        '      <span>auto</span>\n'
        '      <span class="kbd" aria-hidden="true">R</span>\n'
        '    </button>\n'
        '  </div>\n'
        '</header>'
    )


# ---------------------------------------------------------------------------
# KPI helpers + sticky header + KPI section
# ---------------------------------------------------------------------------

_SPARK_COLORS = {
    "running": "var(--run)",
    "failed": "var(--fail)",
    "bypass": "var(--bypass)",
    "done": "var(--done)",
    "pending": "var(--pending)",
}

# Display labels for each KPI kind (CSS handles text-transform: uppercase)
_KPI_LABELS = {
    "running": "Running",
    "failed": "Failed",
    "bypass": "Bypass",
    "done": "Done",
    "pending": "Pending",
}

# Ordered KPI kinds for rendering
_KPI_ORDER = ["running", "failed", "bypass", "done", "pending"]



def _kpi_counts(tasks, features, signals) -> dict:
    """Compute priority-ordered KPI counts: bypass > failed > running > done > pending.

    Invariant: sum(result.values()) == len(tasks) + len(features).

    Priority resolution:
    - bypass_ids: items where item.bypassed is True (state.json)
    - failed_ids: signal kind="failed", excluding bypass_ids
    - running_ids: signal kind="running", excluding bypass_ids and failed_ids
    - done_ids: state.json status=="[xx]" OR signal kind="done", excluding higher buckets
    - pending: remainder

    Done uses state.json as primary source so completed projects display correctly
    even when runtime signal files have been cleaned up.
    """
    all_items = list(tasks or []) + list(features or [])
    if not all_items:
        return {"running": 0, "failed": 0, "bypass": 0, "done": 0, "pending": 0}

    all_ids = {getattr(item, "id", None) for item in all_items if getattr(item, "id", None)}

    # Bypass is determined by the item's own bypassed flag (not signal)
    bypass_ids = {getattr(item, "id", None) for item in all_items
                  if getattr(item, "bypassed", False) and getattr(item, "id", None)}

    raw_failed = _signal_set(signals, "failed")
    raw_running = _signal_set(signals, "running")
    # Done: state.json "[xx]" status is primary; signal files are additive fallback
    state_done_ids = {getattr(item, "id", None) for item in all_items
                      if getattr(item, "status", None) == "[xx]" and getattr(item, "id", None)}
    raw_done = state_done_ids | _signal_set(signals, "done")

    # Apply priority filter: each id is counted only in the highest-priority
    # bucket. Priority order (per docstring): bypass > failed > running > done
    # > pending. A signal file present on a terminal ([xx]) task still wins over
    # the state-derived done bucket — if a worker marks the task running/failed
    # again while it was flagged [xx], that live signal takes precedence.
    failed_ids = (raw_failed & all_ids) - bypass_ids
    running_ids = (raw_running & all_ids) - bypass_ids - failed_ids
    done_ids = (raw_done & all_ids) - bypass_ids - failed_ids - running_ids

    n_bypass = len(bypass_ids)  # bypass_ids is already a subset of all_ids
    n_failed = len(failed_ids)
    n_running = len(running_ids)
    n_done = len(done_ids)
    n_pending = len(all_items) - n_bypass - n_failed - n_running - n_done

    return {
        "running": n_running,
        "failed": n_failed,
        "bypass": n_bypass,
        "done": n_done,
        "pending": max(0, n_pending),
    }


def _spark_buckets(items, kind: str, now: datetime, span_min: int = 10) -> List[int]:
    """Aggregate phase_history events into ``span_min`` 1-minute buckets.

    Bucket index 0 = oldest (now - span_min minutes), last = most recent.
    Events outside the span are ignored. 'pending' kind always returns zeros.

    kind mapping:
    - 'done'    → event == 'xx.ok'
    - 'bypass'  → event == 'bypass'
    - 'failed'  → event.endswith('.fail')
    - 'running' → event.endswith('.ok') and event != 'xx.ok'
    - 'pending' → no mapping (always empty)
    """
    buckets = [0] * span_min
    if kind == "pending":
        return buckets

    start = now - timedelta(minutes=span_min)

    def _matches(event: str) -> bool:
        if not event:
            return False
        if kind == "done":
            return event == "xx.ok"
        if kind == "bypass":
            return event == "bypass"
        if kind == "failed":
            return event.endswith(".fail")
        if kind == "running":
            return event.endswith(".ok") and event != "xx.ok"
        return False

    for item in (items or []):
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            event = getattr(entry, "event", None)
            if not event or not _matches(event):
                continue
            at_dt = _parse_iso_utc(getattr(entry, "at", None))
            if at_dt is None or at_dt < start or at_dt > now:
                continue
            # Bucket index: minutes elapsed from start
            elapsed_minutes = int((at_dt - start).total_seconds() // 60)
            idx = min(elapsed_minutes, span_min - 1)
            buckets[idx] += 1

    return buckets


def _kpi_spark_svg(buckets: List[int], color: str) -> str:
    """Render the legacy-compatible KPI sparkline SVG."""
    n = len(buckets)
    if n == 0:
        buckets = [0]
        n = 1

    max_val = max(buckets)
    total = sum(buckets)
    title_text = f"sparkline: {total} events in last {n} minutes"

    if n < 2 or max_val == 0:
        points = f"0,24 {max(n - 1, 0)},24"
    else:
        points = " ".join(
            f"{i},{24 - (24 * val / max_val):.1f}" for i, val in enumerate(buckets)
        )
    return (
        f'<svg class="spark" viewBox="0 0 {max(n - 1, 0)} 24" aria-hidden="true">'
        f'<title>{_esc(title_text)}</title>'
        f'<polyline points="{points}" stroke="{color}" fill="none" stroke-width="1.5"/>'
        f'</svg>'
    )


def _section_sticky_header(model: dict) -> str:
    """Render the sticky header: logo dot, title, project_root (ellipsis),
    refresh label, and auto-refresh toggle button (style only; JS wired in WP-02).
    """
    project_root = _esc(model.get("project_root", ""))
    refresh_s = _refresh_seconds(model)
    return (
        '<header class="sticky-hdr" data-section="hdr">\n'
        '  <span class="logo-dot" aria-hidden="true">●</span>\n'
        '  <span class="hdr-title">dev-plugin Monitor</span>\n'
        f'  <span class="hdr-project" title="{project_root}">{project_root}</span>\n'
        f'  <span class="hdr-refresh">⟳ {refresh_s}s</span>\n'
        '  <button class="refresh-toggle" aria-pressed="true" tabindex="0">◐ auto</button>\n'
        '</header>'
    )


# v3 CSS-suffix for each KPI kind (matches reference stylesheet .kpi--run etc.)
_KPI_V3_SUFFIX = {
    "running": "run",
    "failed": "fail",
    "bypass": "bypass",
    "done": "done",
    "pending": "pend",
}


def _section_kpi(model: dict) -> str:
    """Render KPI section (v3): section-head + .kpi-strip + filter chips.

    Markup (reference /dev-plugin Monitor.html):
      <section data-section="kpi">
        <div class="section-head">
          <div><div class="eyebrow">overview</div><h2>Task states · …</h2></div>
          <div class="aside">…</div>
        </div>
        <div class="kpi-strip">
          <div class="kpi kpi--run" data-kpi="running">
            <div class="label"><span class="sw"></span>Running</div>
            <div class="num">4</div>
            <div class="delta">+2 / 10m</div>
            <svg class="spark">…</svg>
          </div>
          … ×5 …
        </div>
        <div class="chips">…</div>
      </section>
    """
    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []
    shared_signals = model.get("shared_signals") or []

    counts = _kpi_counts(tasks, features, shared_signals)
    all_items = list(tasks) + list(features)
    now = datetime.now(timezone.utc)
    total_items = len(all_items)

    cards_html = []
    for kind in _KPI_ORDER:
        color = _SPARK_COLORS[kind]
        buckets = _spark_buckets(all_items, kind, now)
        svg = _kpi_spark_svg(buckets, color)
        n = counts[kind]
        label = _KPI_LABELS[kind]
        suffix = _KPI_V3_SUFFIX[kind]
        cards_html.append(
            f'<div class="kpi kpi--{suffix}" data-kpi="{kind}">\n'
            f'  <div class="label"><span class="sw"></span>{label}</div>\n'
            f'  <div class="num" aria-label="{label}: {n}">{n}</div>\n'
            f'  {svg}\n'
            f'</div>'
        )

    # Filter chips with per-status counts (matches reference ·count badge).
    chip_filters = [
        ("all", "All", "true", total_items),
        ("running", "Running", "false", counts["running"]),
        ("failed", "Failed", "false", counts["failed"]),
        ("bypass", "Bypass", "false", counts["bypass"]),
    ]
    chip_htmls = []
    for f, label, pressed, count in chip_filters:
        sw = '<span class="sw"></span>' if f != "all" else ""
        chip_htmls.append(
            f'<button class="chip" data-filter="{f}" aria-pressed="{pressed}" type="button">'
            f'{sw}{label} <span class="ct">{count}</span></button>'
        )
    chips_html = "\n  ".join(chip_htmls)

    cards_block = "\n".join(cards_html)
    eyebrow = "overview"
    heading = "Task states"
    aside = (
        f'<b style="color:var(--accent-hi)">{total_items} items</b>'
        f' · {counts["done"]} done'
    )

    return (
        '<section data-section="kpi" aria-label="Key performance indicators">\n'
        '  <div class="section-head">\n'
        f'    <div><div class="eyebrow">{eyebrow}</div><h2>{heading}</h2></div>\n'
        f'    <div class="aside">{aside}</div>\n'
        '  </div>\n'
        '  <div class="kpi-strip">\n'
        f'{cards_block}\n'
        '  </div>\n'
        '  <div class="chips" data-section="kpi-chips" role="toolbar" aria-label="Task filter">\n'
        f'  {chips_html}\n'
        '  </div>\n'
        '</section>'
    )


def _wp_donut_style(counts: dict) -> str:
    """Return CSS inline style string with --pct-done-end and --pct-run-end variables.

    Calculates degree values for conic-gradient donut chart.
    ``total == 0`` guard prevents ZeroDivisionError and returns 0deg for both.
    """
    done = counts.get("done", 0)
    running = counts.get("running", 0)
    total = done + running + counts.get("failed", 0) + counts.get("bypass", 0) + counts.get("pending", 0)
    if total == 0:
        return "--pct-done-end:0deg; --pct-run-end:0deg;"
    pct_done_end = round(done / total * 360, 1)
    pct_run_end = round((done + running) / total * 360, 1)
    return f"--pct-done-end:{pct_done_end}deg; --pct-run-end:{pct_run_end}deg;"


def _wp_donut_svg(counts: dict) -> str:
    """Return SVG donut chart with stroke-dasharray circles using pathLength=100.

    Renders a track circle + 4 color-slice circles (done/run/fail/bypass).
    pending fills the remainder. Uses stroke-dasharray offset pattern on a
    circle with pathLength="100" for percentage-based drawing.
    Total 0 → returns track-only SVG (no division by zero).
    """
    done = counts.get("done", 0)
    running = counts.get("running", 0)
    failed = counts.get("failed", 0)
    bypass = counts.get("bypass", 0)
    pending = counts.get("pending", 0)
    total = done + running + failed + bypass + pending

    cx, cy, r = 18, 18, 15.9
    stroke_w = 3

    # Track circle (background). var(--bg-3) matches design sample.
    track = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" pathLength="100"'
        f' stroke="var(--bg-3)" stroke-width="{stroke_w}"'
        ' fill="none" stroke-dasharray="100 0"/>'
    )

    if total == 0:
        return (
            '<svg viewBox="0 0 36 36" class="donut-svg">\n'
            f'  {track}\n'
            '</svg>'
        )

    def _pct(n):
        return round(n / total * 100, 2)

    slices = [
        (_pct(done), "var(--done)"),
        (_pct(running), "var(--run)"),
        (_pct(failed), "var(--fail)"),
        (_pct(bypass), "var(--bypass)"),
    ]

    circles = [track]
    offset = 0.0
    for pct, color in slices:
        # Always render the circle even if pct=0 (dasharray "0 100" = invisible)
        # so pathLength="100" count is always track+4 = 5.
        # Rotation to 12-o'clock start handled by CSS `.wp-donut svg {transform:rotate(-90deg)}`,
        # so no per-circle transform needed (matches design HTML).
        safe_pct = max(0, pct)
        dash = f"{safe_pct} {100 - safe_pct}"
        circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" pathLength="100"'
            f' stroke="{color}" stroke-width="{stroke_w}"'
            f' fill="none" stroke-dasharray="{dash}"'
            f' stroke-dashoffset="{-offset:.2f}"/>'
        )
        offset += safe_pct

    inner_html = "\n  ".join(circles)
    return (
        '<svg viewBox="0 0 36 36" class="donut-svg">\n'
        f'  {inner_html}\n'
        '</svg>'
    )


def _trow_data_status(item, running_ids: set, failed_ids: set) -> str:
    """Return the data-status attribute value for a .trow element.

    Priority: bypass > failed > running > done > pending
    Maps _row_state_class output (which uses 'bypass'/'failed'/'running'/'done'/'pending')
    to the same strings used in data-status.
    """
    return _row_state_class(item, running_ids, failed_ids)


def _wp_card_counts(items, running_ids: set, failed_ids: set) -> dict:
    """Return ``{done, running, failed, bypass, pending}`` count dict for *items*.

    Priority (no double-counting, sum == len(items)):
      bypass > failed > running > done > pending

    Delegates state classification to ``_row_state_class`` to avoid duplicating
    the priority logic.
    """
    counts: dict = {"done": 0, "running": 0, "failed": 0, "bypass": 0, "pending": 0}
    for item in items:
        state = _row_state_class(item, running_ids, failed_ids)
        counts[state] += 1
    return counts


def _row_state_class(item, running_ids: set, failed_ids: set) -> str:
    """Return CSS class name for a WorkItem's task-row div.

    Priority: bypass > failed > running > done > pending
    """
    item_id = getattr(item, "id", None)
    if bool(getattr(item, "bypassed", False)):
        return "bypass"
    if item_id and item_id in failed_ids:
        return "failed"
    if item_id and item_id in running_ids:
        return "running"
    if getattr(item, "status", None) == "[xx]":
        return "done"
    return "pending"


def _clean_title(title) -> str:
    """Strip markdown header prefix and limit length for display.

    Features often get their spec.md first line ("# Feature: foo") assigned as
    title — strip the leading '#' chars + "Feature:" marker so the dashboard
    shows a clean human-readable name.
    """
    if not title:
        return ""
    t = str(title).strip()
    while t.startswith("#"):
        t = t[1:].lstrip()
    if t.lower().startswith("feature:"):
        t = t[len("feature:"):].lstrip()
    return t


def _build_state_summary_json(item) -> dict:
    """state.json 요약 dict 를 생성한다 (TSK-02-03 + TSK-02-05 확장).

    포함 필드: status, last_event, last_event_at, elapsed (int초), phase_tail (최근 3개).
    TSK-02-05 추가 필드: model, retry_count, phase_models, escalated.
    item 에 필드가 없으면 graceful default (빈 문자열/None/0/[]).
    """
    status = getattr(item, "status", None)
    last_event = getattr(item, "last_event", None)
    last_event_at = getattr(item, "last_event_at", None)
    elapsed_raw = getattr(item, "elapsed_seconds", None)
    elapsed = (
        int(elapsed_raw)
        if isinstance(elapsed_raw, (int, float)) and not isinstance(elapsed_raw, bool)
        else 0
    )
    history_tail = getattr(item, "phase_history_tail", []) or []
    phase_tail = [
        {
            "event": getattr(e, "event", None),
            "from": getattr(e, "from_status", None),
            "to": getattr(e, "to_status", None),
            "at": getattr(e, "at", None),
            "elapsed_seconds": getattr(e, "elapsed_seconds", None),
        }
        for e in history_tail[-3:]
    ]
    # model chip + escalation badge fields
    item_model = getattr(item, "model", None) or "sonnet"
    rc = _retry_count(item)
    escalated = rc >= _MAX_ESCALATION()
    pm = _phase_models_for(item)
    return {
        "status": status,
        "last_event": last_event,
        "last_event_at": last_event_at,
        "elapsed": elapsed,
        "phase_tail": phase_tail,
        "model": item_model,
        "retry_count": rc,
        "phase_models": pm,
        "escalated": escalated,
    }


def _encode_state_summary_attr(summary: dict) -> str:
    """summary dict 를 JSON → html.escape 로 single-quote 속성에 안전하게 삽입한다 (TSK-02-03).

    반환값은 data-state-summary='...' 의 값 부분이다.
    """
    raw = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    return html.escape(raw, quote=True)


def _trow_info_popover_skeleton() -> str:
    """body 직계에 1회 주입하는 trow info popover DOM 스켈레톤 (TSK-04-02 FR-01).

    ⓘ 버튼 클릭 시 여기에 콘텐츠를 주입하여 보여준다. 기본은 행 위쪽에 배치되고
    상단 여유 부족 시 아래로 폴백한다 (positionPopover JS가 결정).
    """
    return '<div id="trow-info-popover" class="info-popover" role="dialog" hidden></div>'


def _trow_tooltip_skeleton() -> str:
    """Legacy shim — kept for backward compatibility. Returns the new info popover skeleton.

    TSK-04-02 FR-01에서 `#trow-tooltip` hover 툴팁이 `#trow-info-popover` click 팝오버로 대체되었다.
    외부 호출부가 남아있을 수 있으므로 함수는 유지하되 새 스켈레톤을 반환한다.
    """
    return _trow_info_popover_skeleton()


def _render_task_row_v2(item, running_ids: set, failed_ids: set, lang: str = "ko") -> str:
    """Render a v3 ``<div class="trow" data-status="{state}" data-phase="{phase}" data-running="{bool}">`` row.

    Matches reference markup — 7 ``<div>`` children + spinner span:
    ``statusbar / tid / badge / spinner / ttitle / elapsed / retry / flags``.

    TSK-02-01: badge text is DDTR phase label (Design/Build/Test/Done/Failed/Bypass/Pending)
    derived from state.json.status via _phase_label(). data-phase attribute added for CSS/test hooks.
    data-status attribute (signal-based colour mapping) is unchanged.

    TSK-02-02: data-running reflects whether item.id is in running_ids (independent of
    data-status priority). The .spinner span is always emitted as a badge sibling for all
    trows; CSS controls visibility via .trow[data-running="true"] .spinner { display: inline-block }.
    """
    item_id = getattr(item, "id", None)
    bypassed = bool(getattr(item, "bypassed", False))
    error = getattr(item, "error", None)
    title = getattr(item, "title", None)
    status_code = getattr(item, "status", None)
    data_status = _trow_data_status(item, running_ids, failed_ids)
    data_running = "true" if (item_id and item_id in running_ids) else "false"

    # badge text: error counts as failed (same bucket as .failed signal).
    is_failed = bool(error) or (item_id is not None and item_id in failed_ids)
    badge_text = _phase_label(status_code, lang, failed=is_failed, bypassed=bypassed)
    data_phase = _phase_data_attr(status_code, failed=is_failed, bypassed=bypassed)

    badge_title_attr = (
        f' title="{_esc(str(error)[:_ERROR_TITLE_CAP])}"' if error else ""
    )

    elapsed_raw = _format_elapsed(item, lang=lang)
    elapsed_display = elapsed_raw if elapsed_raw != "-" else "—"

    # escalation flag (⚡) — prepend before bypass flag
    rc = _retry_count(item)
    escalated = rc >= _MAX_ESCALATION()
    escalation_span = (
        '<span class="escalation-flag" aria-label="escalated">⚡</span>'
        if escalated else ""
    )
    bypass_span = '<span class="flag f-crit">bypass</span>' if bypassed else ""
    flags_inner = escalation_span + bypass_span

    # model chip — inserted after clean_title in ttitle cell
    item_model_raw = getattr(item, "model", None) or "sonnet"
    model_esc = _esc(item_model_raw)
    model_chip = f'<span class="model-chip" data-model="{model_esc}">{model_esc}</span>'

    # data-domain attribute — used by client-side filter matchesRow()
    domain_val = _esc(getattr(item, "domain", None) or "")

    clean_title = _esc(_clean_title(title))

    # ⓘ info button — opens singleton #trow-info-popover on click.
    info_btn = (
        '<button class="info-btn" type="button"'
        ' aria-label="상세"'
        ' aria-expanded="false"'
        ' aria-controls="trow-info-popover">ⓘ</button>'
    )

    expand_btn = (
        f'<button class="expand-btn" data-task-id="{_esc(item_id or "")}"'
        ' aria-label="Expand" title="Expand">↗</button>'
    )

    _state_summary_encoded = _encode_state_summary_attr(_build_state_summary_json(item))

    return (
        f'<div class="trow" data-status="{data_status}" data-phase="{data_phase}" data-running="{data_running}"'
        f' data-domain="{domain_val}"'
        f' data-task-id="{_esc(item_id or "")}"'
        f" data-state-summary='{_state_summary_encoded}'>\n"
        '  <div class="statusbar"></div>\n'
        f'  <div class="tid id">{_esc(item_id)}</div>\n'
        f'  <div class="badge" data-phase="{data_phase}"{badge_title_attr}>'
        f'{_esc(badge_text)}'
        '<span class="spinner-inline" aria-hidden="true"></span>'
        '</div>\n'
        f'  <div class="ttitle title">{clean_title}{model_chip}</div>\n'
        f'  <div class="elapsed">{_esc(elapsed_display)}</div>\n'
        f'  <div class="retry">×{rc}</div>\n'
        f'  <div class="flags">{flags_inner}</div>\n'
        f'  {info_btn}\n'
        f'  {expand_btn}\n'
        '</div>'
    )


def _merge_badge(ws: dict, lang: str = "ko") -> str:
    """WP 머지 준비도 뱃지 HTML 반환 (TSK-04-03).

    Args:
        ws: merge-status dict. 키: state, stale, pending_count, conflict_count, wp_id, conflicts.
            누락 시 graceful degradation (unknown fallback).
        lang: 'ko' | 'en'

    Returns:
        <button class="merge-badge" data-state="{state}" data-wp="{wp_id}" ...> HTML 문자열.
    """
    state = ws.get("state") or "unknown"
    stale = ws.get("stale", False)
    wp_id = ws.get("wp_id", "")
    pending_count = ws.get("pending_count", 0)
    conflict_count = ws.get("conflict_count", 0)

    if state == "ready":
        emoji = "🟢"
        label = "머지 가능" if lang == "ko" else "Ready"
    elif state == "waiting":
        emoji = "🟡"
        label = f"{pending_count} Task 대기" if lang == "ko" else f"{pending_count} pending"
    elif state == "conflict":
        emoji = "🔴"
        label = f"{conflict_count} 파일 충돌 예상" if lang == "ko" else f"{conflict_count} conflicts"
    elif state == "stale":
        emoji = "🔘"
        label = "확인 필요 (stale)" if lang == "ko" else "Stale"
    else:
        emoji = "🔘"
        label = "확인 필요" if lang == "ko" else "Unknown"
        state = "unknown"

    stale_mark = '<span class="stale">⚠ stale</span>' if stale else ""
    wp_attr = f' data-wp="{_esc(wp_id)}"' if wp_id else ""

    return (
        f'<button class="merge-badge" data-state="{_esc(state)}"{wp_attr}'
        f' aria-label="merge {_esc(state)}">'
        f'{emoji} {_esc(label)}{stale_mark}'
        f'</button>'
    )


def _load_wp_merge_states(docs_dir: str) -> dict:
    """docs_dir/wp-state/{WP-ID}/merge-status.json 파일을 mtime 기반으로 일괄 읽기 (TSK-04-03).

    Returns:
        {WP-ID: merge_status_dict} — 파일 없거나 파싱 실패 시 해당 WP 제외.
    """
    result: dict = {}
    wp_state_dir = Path(docs_dir) / "wp-state"
    if not wp_state_dir.is_dir():
        return result
    for wp_dir in wp_state_dir.iterdir():
        if not wp_dir.is_dir():
            continue
        status_file = wp_dir / "merge-status.json"
        if not status_file.is_file():
            continue
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            result[wp_dir.name] = data
        except Exception:
            # 파싱 실패 → 해당 WP 무시 (graceful degradation)
            pass
    return result

# _wp_busy_indicator_html, _section_wp_cards: moved to monitor_server.renderers.wp [core-renderer-split:C1-1]
# 아래 thin-wrapper는 call-time lazy import로 렌더러를 로드하여 flat-load/순환참조 회피.
# call-time이면 core 모듈 초기화가 완료되어 순환 참조 없이 렌더러를 로드할 수 있다.
def _wp_busy_indicator_html(busy_label: "Optional[str]") -> str:  # type: ignore[misc]
    _wp_mod = _c2b_load_renderer("wp")
    if _wp_mod is not None:
        return _wp_mod._wp_busy_indicator_html(busy_label)
    # fallback: should not reach here in production
    if busy_label is None:
        return ""
    return (
        '<div class="wp-busy-indicator" aria-live="polite">\n'
        f'  <span class="wp-busy-spinner" aria-hidden="true"></span>\n'
        f'  <span class="wp-busy-label">{_esc(busy_label)}</span>\n'
        '</div>'
    )


def _section_wp_cards(*args, **kwargs) -> str:  # type: ignore[misc]
    _wp_mod = _c2b_load_renderer("wp")
    if _wp_mod is not None:
        return _wp_mod._section_wp_cards(*args, **kwargs)
    return ""  # fallback: should not reach here in production


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


def _pane_attr(pane, key: str, default=""):
    """Read ``key`` from a PaneInfo dataclass *or* its ``asdict`` dict form.

    ``_build_state_snapshot`` coerces panes via ``_asdict_or_none`` so the
    dashboard model receives ``list[dict]``; unit tests pass raw dataclasses.
    Support both so the renderer doesn't silently emit empty fields.
    """
    if isinstance(pane, dict):
        return pane.get(key, default)
    return getattr(pane, key, default)


def _is_claude_cli_chrome(line: str) -> bool:
    """Return True iff *line* is part of Claude CLI's bottom chrome.

    The Claude CLI renders a fixed footer at the bottom of every pane:

        ──────────────────── (separator, U+2500 box-drawing)
        ❯                    (prompt, may contain NBSP)
        ──────────────────── (separator)
          [Sonnet 4.6] | branch
          ctx: █▍░░░ 26% | ...
          ⏵⏵ bypass permissions on · N shells

    When we tail the pane for a dashboard preview these 6 lines drown out the
    actual work output.  We detect and strip them so the preview shows
    something meaningful instead.
    """
    stripped = line.strip().rstrip("\xa0").strip()
    if not stripped:
        return False
    # horizontal separator of box-drawing chars (allow stray spaces)
    if "─" in line and all(c in "─ \t" for c in line):
        return True
    # bare prompt
    if stripped == "❯":
        return True
    # status bar lines (always prefixed with two spaces by Claude CLI)
    if line.startswith("  [") and "]" in line:
        return True
    if line.startswith("  ctx:"):
        return True
    if line.startswith("  ⏵⏵") or line.startswith("  ⏸"):
        return True
    return False


def _iter_flat_entry_modules():
    """Yield sys.modules entries whose ``__file__`` ends with ``monitor-server.py``.

    Tests load the thin entry file via ``spec_from_file_location(<alias>, ...)``
    under arbitrary alias names (e.g. ``monitor_server_pane_size``). When a
    test applies ``mock.patch.object`` to the flat entry module, core-level
    functions need to honour those patches — we do so by sweeping ``sys.modules``
    for any module whose source file is the thin entry.
    """
    import os as _os
    for _mod_obj in list(sys.modules.values()):
        try:
            _f = getattr(_mod_obj, "__file__", None)
        except Exception:  # noqa: BLE001
            continue
        if not _f:
            continue
        try:
            if _os.path.basename(_f) == "monitor-server.py":
                yield _mod_obj
        except (TypeError, ValueError):
            continue


def _pane_last_n_lines(pane_id: str, n: int = _PANE_PREVIEW_LINES) -> str:
    """Return the last *n* non-chrome lines from a tmux pane's scrollback.

    Calls ``capture_pane(pane_id)``, strips trailing Claude CLI chrome
    (status bar, prompt separators) and whitespace-only lines from the tail,
    then returns the last *n* remaining lines.  Returns an empty string on
    any error or when the result is entirely blank/chrome.
    """
    # Look up capture_pane via flat entry modules first so that test mocks
    # applied to spec_from_file_location("…", "monitor-server.py") are honoured.
    _capture = capture_pane
    for _entry in _iter_flat_entry_modules():
        _mock = getattr(_entry, "capture_pane", None)
        if _mock is not None and _mock is not capture_pane:
            _capture = _mock
            break
    try:
        raw = _capture(pane_id)
    except Exception:
        return ""
    # rstrip removes trailing whitespace/newlines; splitlines() handles all
    # line-ending variants and produces no trailing empty element.
    lines = raw.rstrip().splitlines()
    # Strip trailing CLI chrome + blank lines so the preview shows actual work.
    while lines and (not lines[-1].strip() or _is_claude_cli_chrome(lines[-1])):
        lines.pop()
    if not lines:
        return ""
    return "\n".join(lines[-n:])


# moved to monitor_server.renderers.team [core-renderer-split:C1-2]
def _render_pane_row(pane, preview_lines: "Optional[str]" = "") -> str:
    _team_mod = _c2b_load_renderer("team")
    if _team_mod is not None:
        return _team_mod._render_pane_row(pane, preview_lines)
    # fallback: minimal shim (flat-load context before renderers available)
    pane_id_raw = _pane_attr(pane, "pane_id", "")
    pane_id_esc = _esc(pane_id_raw)
    cmd = _esc(_pane_attr(pane, "pane_current_command", ""))
    pid = _esc(_pane_attr(pane, "pane_pid", ""))
    window_name = _esc(_pane_attr(pane, "window_name", ""))
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
        f'    <a class="mini-btn" href="/pane/{pane_id_esc}">show output</a>\n'
        f'    <button class="mini-btn primary" type="button"'
        f' data-pane-expand="{pane_id_esc}"'
        f' aria-label="Expand pane {pane_id_esc}">expand <span class="kbd">&#x21B5;</span></button>\n'
        f'  </div>\n'
        f'{preview_html}\n'
        '</div>'
    )


_TOO_MANY_PANES_THRESHOLD = 20


# moved to monitor_server.renderers.team [core-renderer-split:C1-2]
def _section_team(panes, heading: "Optional[str]" = None) -> str:
    _team_mod = _c2b_load_renderer("team")
    if _team_mod is not None:
        return _team_mod._section_team(panes, heading)
    return ""


# moved to monitor_server.renderers.subagents [core-renderer-split:C1-3]
_SUBAGENT_INFO = (
    '<p class="info">agent-pool subagents run inside the parent Claude session'
    ' — output capture is unavailable (signals only).</p>'
)


def _render_subagent_row(sig) -> str:
    _sub_mod = _c2b_load_renderer("subagents")
    if _sub_mod is not None:
        return _sub_mod._render_subagent_row(sig)
    # fallback shim
    kind = getattr(sig, "kind", "")
    task_id = getattr(sig, "task_id", "")
    state_map = {"running": "running", "done": "done", "failed": "failed", "bypassed": "done"}
    data_state = state_map.get(kind, "pending")
    return (
        f'<span class="sub" data-state="{data_state}">'
        f'<span class="sw"></span>'
        f'{_esc(task_id)}'
        f'<span class="n">{_esc(kind if kind else "?")}</span>'
        f'</span>'
    )


def _section_subagents(signals, heading: "Optional[str]" = None) -> str:
    _sub_mod = _c2b_load_renderer("subagents")
    if _sub_mod is not None:
        return _sub_mod._section_subagents(signals, heading)
    return ""


def _status_class_for_phase(status_str: str) -> str:
    """Map '[xx]'/'[im]' etc. to CSS class name for the history table."""
    _map = {
        "[ ]": "init",
        "[dd]": "dd",
        "[im]": "im",
        "[ts]": "ts",
        "[xx]": "done",
    }
    if not status_str:
        return ""
    return _map.get(status_str.strip(), "")


def _section_phase_history(tasks, features) -> str:
    """Phase-history section: most recent events as v3 <table> (cap 10).

    v3: <div class="history" data-section="phases"> wraps a <table> with
    columns: #, time, task-id, event, from→to, elapsed.
    Empty → old-style empty section (no table).
    """
    collected: list = []
    for item in list(tasks or []) + list(features or []):
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            collected.append((getattr(item, "id", "?"), entry))

    collected.sort(key=lambda pair: getattr(pair[1], "at", "") or "", reverse=True)
    top = collected[:_PHASES_SECTION_LIMIT]

    if not top:
        return _empty_section("phases", "Recent Phase History", "no phase history yet")

    rows = []
    for idx, (item_id, entry) in enumerate(top, 1):
        at = _esc(getattr(entry, "at", ""))
        event = _esc(getattr(entry, "event", ""))
        from_s_raw = getattr(entry, "from_status", "") or ""
        to_s_raw = getattr(entry, "to_status", "") or ""
        from_s = _esc(from_s_raw)
        to_s = _esc(to_s_raw)
        elapsed = getattr(entry, "elapsed_seconds", None)
        elapsed_str = _esc(str(elapsed) + "s" if elapsed is not None else "-")
        to_cls = _status_class_for_phase(to_s_raw)
        to_cell = f'<span class="to {to_cls}">{to_s}</span>' if to_cls else f'<span class="to">{to_s}</span>'

        rows.append(
            f'<tr>'
            f'<td class="idx">{idx}</td>'
            f'<td class="t">{at}</td>'
            f'<td class="tid">{_esc(item_id)}</td>'
            f'<td class="ev">{event}</td>'
            f'<td class="arr">{from_s} → {to_cell}</td>'
            f'<td class="el">{elapsed_str}</td>'
            f'</tr>'
        )

    table_html = (
        '<table>\n'
        '  <thead><tr>'
        '<th class="idx">#</th>'
        '<th class="t">time</th>'
        '<th class="tid">id</th>'
        '<th class="ev">event</th>'
        '<th class="arr">transition</th>'
        '<th class="el">elapsed</th>'
        '</tr></thead>\n'
        '  <tbody>\n'
        + "\n".join(f'  {r}' for r in rows)
        + '\n  </tbody>\n'
        '</table>'
    )

    return (
        '<div class="history" data-section="phases" id="phases">\n'
        '  <h2>Recent Phase History</h2>\n'
        + table_html
        + '\n</div>'
    )


# ---------------------------------------------------------------------------
# Dependency Graph section (SSR skeleton + vendor scripts)
# ---------------------------------------------------------------------------


def _section_dep_graph(lang: str = "ko", subproject: str = "all") -> str:
    """Render the Dependency Graph section SSR skeleton (TRD §3.9.5).

    Returns a ``<section id="dep-graph">`` block containing:
    - ``.section-head`` with i18n h2 + ``<aside id="dep-graph-summary">``
    - ``.dep-graph-wrap``: canvas div (height 520px) + legend div
    - 4 vendor ``<script>`` tags in load order:
      dagre → cytoscape → cytoscape-dagre → graph-client

    The ``subproject`` value is HTML-escaped and injected as
    ``data-subproject="..."`` on the root ``<section>`` element so that
    graph-client.js can read it without inline scripts.
    """
    sp_esc = html.escape(subproject or "all", quote=True)
    heading = _t(lang, "dep_graph")

    # SSR chip markup with i18n labels.
    # graph-client.js:updateSummary uses [data-stat] selector — tag change
    # (<span>→<b>) is intentional and selector-compatible.
    _STAT_STATES = ("total", "done", "running", "pending", "failed", "bypassed")
    chips = " ".join(
        f'<span class="dep-stat dep-stat-{s}">'
        f'<em>{html.escape(_t(lang, f"dep_stat_{s}"))}</em>'
        f' <b data-stat="{s}">-</b></span>'
        for s in _STAT_STATES
    )
    summary_html = f'<aside id="dep-graph-summary" class="dep-graph-summary">{chips}</aside>'

    wheel_label = html.escape(_t(lang, "dep_wheel_zoom"))
    # Critical Path 항목을 Failed 와 별도 <li>로 분리. <div>/<span> → <ul>/<li> 전환.
    legend_html = (
        '<ul id="dep-graph-legend" class="dep-graph-legend">'
        '<li class="legend-done leg-item" style="color:#22c55e">&#9632; done</li>'
        '<li class="legend-running leg-item" style="color:#eab308">&#9632; running</li>'
        '<li class="legend-pending leg-item" style="color:#94a3b8">&#9632; pending</li>'
        '<li class="legend-failed leg-item" style="color:#ef4444">&#9632; failed</li>'
        '<li class="legend-bypassed leg-item" style="color:#a855f7">&#9632; bypassed</li>'
        '<li class="legend-critical leg-item" style="color:#f59e0b">&#9632; critical path</li>'
        '<label class="dep-graph-wheel" for="dep-graph-wheel-toggle">'
        '<input type="checkbox" id="dep-graph-wheel-toggle">'
        f'<span>{wheel_label}</span></label>'
        '</ul>'
    )

    # graph-client.js는 개발 중 자주 바뀌므로 mtime 기반 cache-buster를 붙여 브라우저 캐시를 무효화한다.
    try:
        from pathlib import Path as _Path
        _plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(_Path(__file__).resolve().parents[2])
        _gc_path = _Path(_plugin_root) / "skills" / "dev-monitor" / "vendor" / "graph-client.js"
        _gc_ver = str(int(_gc_path.stat().st_mtime))
    except OSError:
        _gc_ver = "0"

    scripts_html = (
        '<script src="/static/dagre.min.js"></script>\n'
        '<script src="/static/cytoscape.min.js"></script>\n'
        '<script src="/static/cytoscape-node-html-label.min.js"></script>\n'
        '<script src="/static/cytoscape-dagre.min.js"></script>\n'
        f'<script src="/static/graph-client.js?v={_gc_ver}"></script>'
    )

    return (
        f'<section id="dep-graph" data-section="dep-graph"'
        f' data-subproject="{sp_esc}">\n'
        '  <div class="section-head">\n'
        f'    <div><h2>{html.escape(heading)}</h2></div>\n'
        f'    {summary_html}\n'
        '  </div>\n'
        '  <div class="dep-graph-wrap">\n'
        '    <div id="dep-graph-canvas" style="min-height:640px; height:clamp(640px, 78vh, 1400px);"></div>\n'
        f'    {legend_html}\n'
        '  </div>\n'
        f'{scripts_html}\n'
        '</section>'
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Live Activity render functions
# ---------------------------------------------------------------------------

_KNOWN_PHASES = {"dd", "im", "ts", "xx"}
_LIVE_ACTIVITY_LIMIT = 20


def _parse_iso_utc(s):
    """ISO 8601 문자열을 UTC-aware datetime으로 파싱한다.

    'Z' 접미사를 '+00:00'으로 정규화하고, naive datetime에는 timezone.utc를 부여한다.
    None/빈문자열/파싱 실패 시 None 반환 (예외 없음).
    """
    if not s:
        return None
    try:
        normalized = s.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return None


# moved to monitor_server.renderers.activity [core-renderer-split:C1-4]
def _fmt_hms(dt):
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._fmt_hms(dt)
    return dt.astimezone(timezone.utc).strftime("%H:%M:%S")


def _fmt_elapsed_short(seconds):
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._fmt_elapsed_short(seconds)
    if seconds is None:
        return "-"
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    if total < 60:
        return str(total) + "s"
    if total < 3600:
        m, s = divmod(total, 60)
        return str(m) + "m " + str(s) + "s"
    h, rem = divmod(total, 3600)
    m = rem // 60
    return str(h) + "h " + str(m) + "m"


def _event_to_sig_kind(event: "Optional[str]") -> "Optional[str]":
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._event_to_sig_kind(event)
    if not event:
        return None
    if event == "bypass":
        return "bypassed"
    if event.endswith(".fail"):
        return "failed"
    if event.endswith(".done"):
        return "done"
    return None


def _live_activity_rows(tasks, features, limit=_LIVE_ACTIVITY_LIMIT):
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._live_activity_rows(tasks, features, limit)
    return []


def _live_activity_details_wrap(heading: str, body: str) -> str:
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._live_activity_details_wrap(heading, body)
    return body


def _arow_data_to(event: "Optional[str]", to_s: "Optional[str]") -> str:
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._arow_data_to(event, to_s)
    return "pending"


def _render_arow(item_id: str, entry, dt, sig_content: dict) -> str:
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._render_arow(item_id, entry, dt, sig_content)
    return ""


def _section_live_activity(model, heading: "Optional[str]" = None):
    _act_mod = _c2b_load_renderer("activity")
    if _act_mod is not None:
        return _act_mod._section_live_activity(model, heading)
    return ""


def _phase_label_history(status_str):
    """Map '[dd]'/'[im]'/'[ts]'/'[xx]' to lowercase phase labels for history rows.

    Used by activity section from→to labels. Not to be confused with the badge
    helper _phase_label(status_code, lang, *, failed, bypassed) defined earlier.
    """
    if not status_str:
        return ""
    _map = {
        "[ ]": "pending",
        "[dd]": "design",
        "[im]": "build",
        "[ts]": "test",
        "[xx]": "done",
    }
    return _map.get(str(status_str).strip(), str(status_str))


def _phase_of(to_status):
    """'[dd]' 형태의 to_status를 phase 문자열로 변환한다. 알 수 없으면 None."""
    if not to_status:
        return None
    stripped = to_status.strip()
    if len(stripped) >= 3 and stripped[0] == "[" and stripped[-1] == "]":
        phase = stripped[1:-1]
        if phase in _KNOWN_PHASES:
            return phase
    return None


# Compiled once at module load; used by _wrap_with_data_section.
_DATA_SECTION_TAG_RE = re.compile(r'(<(?:section|header)(\s[^>]*)?>)', re.DOTALL)


# ---------------------------------------------------------------------------
# WP-02: Client-side dashboard JS (filter chips, auto-refresh, drawer polling)
# ---------------------------------------------------------------------------
_DASHBOARD_JS = """\
(function(){
  'use strict';
  /* shared state — dashboard poll + drawer poll are fully independent */
  var state={
    autoRefresh:true,activeFilter:'all',mainPollId:null,mainAbort:null,
    drawerPaneId:null,drawerPollId:null,clockId:null,
    /* monitor-perf: visibility-aware polling + ETag 캐시 */
    visible:(document.visibilityState!=='hidden'),mainEtag:''
  };
  /* ---- clock (v3) ---- */
  function startClock(){
    var clock=document.getElementById('clock');
    if(!clock)return;
    state.clockId=setInterval(function(){
      var now=new Date();
      clock.textContent=now.toISOString().slice(0,19).replace('T',' ')+'Z';
    },1000);
  }
  /* ---- fold persistence (TSK-00-01 generic + TSK-05-01/TSK-01-02 data-wp 호환) ---- */
  var FOLD_KEY_PREFIX='dev-monitor:fold:';
  function readFold(key, defaultOpen){
    try{
      var v=localStorage.getItem(FOLD_KEY_PREFIX+key);
      if(v==='open')return true;
      if(v==='closed')return false;
      return defaultOpen===undefined?false:defaultOpen;
    }catch(e){return defaultOpen===undefined?false:defaultOpen;}
  }
  function writeFold(key, open){
    try{localStorage.setItem(FOLD_KEY_PREFIX+key,open?'open':'closed');}catch(e){}
  }
  function _foldKeyOf(el){
    /* data-fold-key 우선, 하위 호환으로 data-wp도 지원 */
    return el.getAttribute('data-fold-key')||el.getAttribute('data-wp');
  }
  function applyFoldStates(container){
    container.querySelectorAll('[data-fold-key],[data-wp]').forEach(function(el){
      var key=_foldKeyOf(el);
      if(!key)return;
      var defaultOpen=el.hasAttribute('data-fold-default-open');
      var isOpen=readFold(key, defaultOpen);
      if(isOpen){el.setAttribute('open','');}
      else{el.removeAttribute('open');}
    });
  }
  function bindFoldListeners(container){
    container.querySelectorAll('[data-fold-key],[data-wp]').forEach(function(el){
      if(el.__foldBound)return;
      el.__foldBound=true;
      el.addEventListener('toggle',function(){
        var key=_foldKeyOf(el);
        if(key)writeFold(key, el.open);
      });
    });
  }
  /* ---- body[data-filter] CSS-driven filter (v3) ---- */
  function applyFilter(){
    var f=state.activeFilter;
    document.body.setAttribute('data-filter',f);
    /* legacy: also patch chip aria-pressed */
    document.querySelectorAll('.chip[data-filter]').forEach(function(c){
      c.setAttribute('aria-pressed',c.dataset.filter===f?'true':'false');
    });
  }
  /* ---- filter chips (TSK-02-02) — event delegation survives DOM replacement ---- */
  document.addEventListener('click',function(e){
    var chip=e.target.closest?e.target.closest('.chip'):null;
    if(!chip)return;
    state.activeFilter=chip.dataset.filter||'all';
    applyFilter();
  });
  /* ---- auto-refresh toggle (TSK-02-02) ---- */
  document.addEventListener('click',function(e){
    var tog=e.target.closest?e.target.closest('.refresh-toggle'):null;
    if(!tog)return;
    state.autoRefresh=!state.autoRefresh;
    tog.setAttribute('aria-pressed',String(state.autoRefresh));
    tog.textContent=state.autoRefresh?'◐ auto':'○ paused';
    if(!state.autoRefresh){stopMainPoll();}else{startMainPoll();}
  });
  /* ---- dashboard polling (TSK-02-01, monitor-perf: visibility-aware) ---- */
  /* monitor-perf (2026-04-24): visible 상태 초기화 + data-anim 토글로 무한 CSS 애니메이션 일괄 정지 */
  state.visible=(document.visibilityState!=='hidden');
  try{document.documentElement.setAttribute('data-anim',state.visible?'on':'off');}catch(_){}
  function onMonitorVisibilityChange(){
    state.visible=(document.visibilityState!=='hidden');
    try{document.documentElement.setAttribute('data-anim',state.visible?'on':'off');}catch(_){}
    if(!state.visible){stopMainPoll();}
    else if(state.autoRefresh){startMainPoll();}
  }
  document.addEventListener('visibilitychange',onMonitorVisibilityChange);
  function stopMainPoll(){
    if(state.mainPollId!==null){clearInterval(state.mainPollId);state.mainPollId=null;}
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){} state.mainAbort=null;}
  }
  function startMainPoll(){
    stopMainPoll();
    /* monitor-perf: hidden 탭에서는 폴링 시작 안 함 */
    if(!state.visible)return;
    tick();
    state.mainPollId=setInterval(tick,5000);
  }
  function tick(){
    if(!state.autoRefresh)return;
    /* monitor-perf: visibilityState hidden이면 폴링 스킵 */
    if(!state.visible)return;
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){}}
    state.mainAbort=new AbortController();
    fetchAndPatch(state.mainAbort.signal);
  }
  function fetchAndPatch(signal){
    /* monitor-perf (2026-04-24): If-None-Match로 ETag 보낸 뒤 304면 전체 스킵.
       서버 SSR HTML이 변하지 않았을 때 76KB 재전송·DOMParser·patchSection 모두 0. */
    var headers={'If-None-Match':state.mainEtag||''};
    fetch(window.location.search?'/'+window.location.search:'/',{cache:'no-store',signal:signal,headers:headers})
      .then(function(r){
        if(r.status===304)return null;
        var etag=r.headers.get('ETag');
        if(etag)state.mainEtag=etag;
        return r.ok?r.text():null;
      })
      .then(function(text){
        if(!text)return;
        var parser=new DOMParser();
        var newDoc=parser.parseFromString(text,'text/html');
        var newSections=newDoc.querySelectorAll('[data-section]');
        newSections.forEach(function(newEl){
          var name=newEl.getAttribute('data-section');
          patchSection(name,newEl.innerHTML);
        });
        /* TSK-02-02: DOM 교체 후 필터 재적용 */
        applyFilter();
      })
      .catch(function(){/* silent: retry on next tick */});
  }
  function patchSection(name,newHtml){
    var current=document.querySelector('[data-section="'+name+'"]');
    if(!current)return;
    /* dep-graph is managed autonomously by graph-client.js; skip DOM replacement
       to prevent cytoscape canvas destruction on every 5-second dashboard poll. */
    if(name==='dep-graph')return;
    /* TSK-05-01: filter-bar controls must survive auto-refresh DOM replacement.
       The filter-bar section is static SSR content — inputs hold client state.
       Replacing its innerHTML would lose user-typed query/select values. */
    if(name==='filter-bar')return;
    if(name==='hdr'){
      /* Preserve chip aria-pressed states and refresh-toggle visual state
         across DOM replacement so client-side filter/toggle survive server push. */
      var chipStates={};
      current.querySelectorAll('.chip[data-filter]').forEach(function(c){
        chipStates[c.dataset.filter]=c.getAttribute('aria-pressed');
      });
      var togEl=current.querySelector('.refresh-toggle');
      var togPressed=togEl?togEl.getAttribute('aria-pressed'):null;
      var togText=togEl?togEl.textContent:null;
      if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
      /* Restore chip states */
      current.querySelectorAll('.chip[data-filter]').forEach(function(c){
        var saved=chipStates[c.dataset.filter];
        if(saved!==null&&saved!==undefined){c.setAttribute('aria-pressed',saved);}
      });
      /* Restore refresh-toggle state */
      var tog2=current.querySelector('.refresh-toggle');
      if(tog2&&togPressed!==null){
        tog2.setAttribute('aria-pressed',togPressed);
        if(togText){tog2.textContent=togText;}
      }
      return;
    }
    /* TSK-05-01 / TSK-01-02: fold 상태 복원이 필요한 섹션 집합.
       새 섹션 추가 시 이 집합에만 추가하면 된다. */
    var _FOLD_SECTIONS={'wp-cards':1,'live-activity':1};
    if(_FOLD_SECTIONS[name]){
      if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
      applyFoldStates(current);
      bindFoldListeners(current);
      return;
    }
    if(current.innerHTML!==newHtml){current.innerHTML=newHtml;}
  }
  /* ---- drawer control (v3: aria-hidden="false" + focus trap) ---- */
  function _setDrawerOpen(open){
    var backdrop=document.querySelector('[data-drawer-backdrop]');
    var panel=document.querySelector('[data-drawer]');
    if(backdrop){backdrop.setAttribute('aria-hidden',open?'false':'true');}
    if(panel){
      panel.setAttribute('aria-hidden',open?'false':'true');
      /* focus-trap: set tabindex=-1 on focusables when closed */
      panel.querySelectorAll('[tabindex]').forEach(function(el){
        el.setAttribute('tabindex',open?'0':'-1');
      });
      if(open){
        var first=panel.querySelector('[tabindex="0"]');
        /* preventScroll: drawer is position:fixed; without this Chromium will
           scroll the page body to "reveal" the focused element, landing the
           user at the very bottom of the dashboard with only one line visible. */
        if(first){try{first.focus({preventScroll:true});}catch(_){first.focus();}}
      }
    }
  }
  function openDrawer(paneId){
    state.drawerPaneId=paneId;
    var titleEl=document.querySelector('[data-drawer-title]');
    if(titleEl){titleEl.textContent='Pane: '+paneId;}
    _setDrawerOpen(true);
    startDrawerPoll();
  }
  function closeDrawer(){
    state.drawerPaneId=null;
    stopDrawerPoll();
    _setDrawerOpen(false);
  }
  function stopDrawerPoll(){
    if(state.drawerPollId!==null){clearInterval(state.drawerPollId);state.drawerPollId=null;}
  }
  function startDrawerPoll(){
    stopDrawerPoll();
    tickDrawer();
    state.drawerPollId=setInterval(tickDrawer,2000);
  }
  function tickDrawer(){
    var id=state.drawerPaneId;
    if(!id)return;
    fetch('/api/pane/'+encodeURIComponent(id),{cache:'no-store'})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){if(j)updateDrawerBody(j);})
      .catch(function(){/* silent: retry on next tick */});
  }
  function updateDrawerBody(j){
    var pre=document.querySelector('[data-drawer-pre]');
    if(!pre)return;
    /* Preserve body scroll: some browsers reflow page scroll when a focused
       element's scrollable content changes. Snapshot + restore is cheap. */
    var prevBodyY=window.scrollY||0;
    pre.textContent=(j.lines||[]).join('\\n');
    /* rAF ensures layout has computed scrollHeight/clientHeight for the new
       text before we seek. Clamp explicitly so we land at "bottom minus one
       viewport" — the last clientHeight worth of lines stays visible. */
    requestAnimationFrame(function(){
      var sh=pre.scrollHeight||0;
      var ch=pre.clientHeight||0;
      pre.scrollTop=Math.max(0,sh-ch);
      if(window.scrollY!==prevBodyY){window.scrollTo(0,prevBodyY);}
    });
    var meta=document.querySelector('[data-drawer-meta]');
    if(meta){meta.textContent=j.captured_at||'';}
  }
  /* ---- event delegation (click + keydown) ---- */
  function _hasAttr(el,attr){return el&&el.hasAttribute&&el.hasAttribute(attr);}
  document.addEventListener('click',function(e){
    var t=e.target;
    var exp=t.closest?t.closest('[data-pane-expand]'):(_hasAttr(t,'data-pane-expand')?t:null);
    if(exp){openDrawer(exp.getAttribute('data-pane-expand'));return;}
    if(_hasAttr(t,'data-drawer-close')||_hasAttr(t,'data-drawer-backdrop')){closeDrawer();}
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&state.drawerPaneId){closeDrawer();}
  });
  /* ---- init ---- */
  function init(){
    /* v3: start clock */
    startClock();
    /* v3: apply initial body[data-filter] */
    applyFilter();
    /* TSK-02-02: refresh-toggle 버튼 초기 상태 동기화 */
    var tog=document.querySelector('.refresh-toggle');
    if(tog){
      state.autoRefresh=(tog.getAttribute('aria-pressed')!=='false');
      tog.textContent=state.autoRefresh?'◐ auto':'○ paused';
    }
    /* TSK-05-01: fold 상태 복원 (startMainPoll 직전) */
    applyFoldStates(document);
    bindFoldListeners(document);
    startMainPoll();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init);
  }else{
    init();
  }
})();

/* TSK-05-01: Filter bar — currentFilters / matchesRow / applyFilters / syncUrl / loadFiltersFromUrl */
/* patchSection monkey-patch for filter survival across 5-second auto-refresh */
(function setupFilterBar(){
  'use strict';
  /* ---- 5 core filter functions ---- */
  function currentFilters(){
    var q      =(document.getElementById('fb-q')||{value:''}).value.trim().toLowerCase();
    var status =(document.getElementById('fb-status')||{value:''}).value;
    var domain =(document.getElementById('fb-domain')||{value:''}).value;
    var model  =(document.getElementById('fb-model')||{value:''}).value;
    return {q:q,status:status,domain:domain,model:model};
  }
  function matchesRow(trow,f){
    /* q: substring match on task-id OR .ttitle text, case-insensitive */
    if(f.q){
      var taskId=(trow.dataset.taskId||'').toLowerCase();
      var titleEl=trow.querySelector('.ttitle');
      var titleText=titleEl?titleEl.textContent.toLowerCase():'';
      if(taskId.indexOf(f.q)===-1&&titleText.indexOf(f.q)===-1)return false;
    }
    /* status: exact match on data-status OR data-phase */
    if(f.status){
      var ds=trow.dataset.status||'';
      var dp=trow.dataset.phase||'';
      if(ds!==f.status&&dp!==f.status)return false;
    }
    /* domain: exact match on data-domain */
    if(f.domain){
      if((trow.dataset.domain||'')!==f.domain)return false;
    }
    /* model: exact match on .model-chip data-model */
    if(f.model){
      var chip=trow.querySelector('.model-chip');
      if((chip?chip.dataset.model||'':'')!==f.model)return false;
    }
    return true;
  }
  function applyFilters(){
    var f=currentFilters();
    /* .trow[data-task-id] — task rows carry data-task-id on the outer div. */
    document.querySelectorAll('.trow[data-task-id]').forEach(function(trow){
      trow.style.display=matchesRow(trow,f)?'':'none';
    });
    /* Dep-Graph filter — optional, guard for missing depGraph */
    if(window.depGraph&&typeof window.depGraph.applyFilter==='function'){
      window.depGraph.applyFilter(function(nodeId){
        /* nodeId matches task id — show node if no q filter or task matches */
        if(!f.q&&!f.domain&&!f.model&&!f.status)return true;
        var trow=document.querySelector('.trow[data-task-id="'+nodeId+'"]');
        if(!trow)return true;/* unknown node — keep visible */
        return matchesRow(trow,f);
      });
    }
  }
  /* Apply filters and sync URL — shared by all event handlers */
  function applyAndSync(){applyFilters();syncUrl(currentFilters());}
  function syncUrl(f){
    var url=new URL(window.location.href);
    var sp=url.searchParams;
    /* Set or delete each filter param; preserve subproject/lang/other params */
    if(f.q){sp.set('q',f.q);}else{sp.delete('q');}
    if(f.status){sp.set('status',f.status);}else{sp.delete('status');}
    if(f.domain){sp.set('domain',f.domain);}else{sp.delete('domain');}
    if(f.model){sp.set('model',f.model);}else{sp.delete('model');}
    history.replaceState(null,'',url.toString());
  }
  /* Get the 4 filter control DOM elements */
  function _fbEls(){
    return {
      q:document.getElementById('fb-q'),
      st:document.getElementById('fb-status'),
      dm:document.getElementById('fb-domain'),
      md:document.getElementById('fb-model')
    };
  }
  function loadFiltersFromUrl(){
    var sp=new URLSearchParams(window.location.search);
    var els=_fbEls();
    if(els.q&&sp.has('q')){els.q.value=sp.get('q');}
    if(els.st&&sp.has('status')){els.st.value=sp.get('status');}
    if(els.dm&&sp.has('domain')){els.dm.value=sp.get('domain');}
    if(els.md&&sp.has('model')){els.md.value=sp.get('model');}
  }
  /* ---- event bindings (document-level delegation — survives DOM replacement) ---- */
  document.addEventListener('input',function(e){
    if(e.target&&e.target.id==='fb-q'){applyAndSync();}
  });
  document.addEventListener('change',function(e){
    var id=e.target&&e.target.id;
    if(id==='fb-status'||id==='fb-domain'||id==='fb-model'){applyAndSync();}
  });
  document.addEventListener('click',function(e){
    if(e.target&&e.target.id==='fb-reset'){
      var els=_fbEls();
      if(els.q)els.q.value='';
      if(els.st)els.st.value='';
      if(els.dm)els.dm.value='';
      if(els.md)els.md.value='';
      applyAndSync();
    }
  });
  /* ---- patchSection monkey-patch — filter survival across auto-refresh ---- */
  /* Extract helper: registers monkey-patch once (sentinel guard). */
  function _registerPatchWrap(){
    if(window.patchSection&&!window.patchSection.__filterWrapped){
      var _orig=window.patchSection;
      window.patchSection=function(name,html){
        _orig.call(this,name,html);
        /* wp-cards와 live-activity 섹션만 .trow를 포함 — 다른 섹션 patch 후에는 재필터링 불필요. */
        if(name==='wp-cards'||name==='live-activity'){applyFilters();}
      };
      window.patchSection.__filterWrapped=true;
    }
  }
  _registerPatchWrap();
  /* ---- initial load sequence (DOMContentLoaded) ---- */
  function initFilterBar(){
    loadFiltersFromUrl();
    applyFilters();
    /* Re-register monkey-patch here if patchSection was not yet available at IIFE run time. */
    _registerPatchWrap();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initFilterBar);
  }else{
    initFilterBar();
  }
  /* Expose for external access (e.g. dev-test verification) */
  window.filterBar={currentFilters:currentFilters,matchesRow:matchesRow,applyFilters:applyFilters,syncUrl:syncUrl,loadFiltersFromUrl:loadFiltersFromUrl};
})();

/* TSK-04-02 FR-01: Task info popover — setupInfoPopover IIFE (click trigger, above-row placement) */
/* TSK-02-05: renderPhaseModels 확장 유지 */
function renderPhaseModels(pm,escalated,retry_count){
  if(!pm)return null;
  var dl=document.createElement('dl');
  dl.className='phase-models';
  function pmrow(label,value){
    var dt=document.createElement('dt');dt.textContent=label;
    var dd=document.createElement('dd');dd.textContent=value||'—';
    dl.appendChild(dt);dl.appendChild(dd);
  }
  pmrow('Design',pm.design);
  pmrow('Build',pm.build);
  var testLine=escalated
    ?'haiku → '+pm.test+' (retry #'+retry_count+') ⚡'
    :pm.test;
  pmrow('Test',testLine);
  pmrow('Refactor',pm.refactor);
  return dl;
}

function renderInfoPopoverHtml(data){
  var dl=document.createElement('dl');
  function row(label,value){
    var dt=document.createElement('dt');dt.textContent=label;
    var dd=document.createElement('dd');dd.textContent=(value===null||value===undefined)?'—':String(value);
    dl.appendChild(dt);dl.appendChild(dd);
  }
  row('status',data.status);
  row('last event',data.last_event);
  row('at',data.last_event_at);
  row('elapsed',data.elapsed!=null?data.elapsed+'s':null);
  if(data.phase_tail&&data.phase_tail.length){
    var dt2=document.createElement('dt');dt2.textContent='recent phases';
    dl.appendChild(dt2);
    data.phase_tail.forEach(function(p){
      var dd2=document.createElement('dd');
      dd2.textContent=(p.event||'')+(p.from?' '+p.from+' → ':'')+( p.to||'');
      dl.appendChild(dd2);
    });
  }
  var pmDl=renderPhaseModels(data.phase_models,data.escalated,data.retry_count);
  var frag=document.createDocumentFragment();
  frag.appendChild(dl);
  if(pmDl){frag.appendChild(pmDl);}
  return frag;
}

function positionPopover(btn,pop){
  /* Position above row by default; flip below on insufficient top space. Uses scrollY/scrollX. */
  var sy=window.scrollY,sx=window.scrollX;
  var row=btn.closest?btn.closest('.trow'):null;
  var anchor=row||btn;
  var r=anchor.getBoundingClientRect();
  var prevHidden=pop.hidden;
  pop.hidden=false;
  pop.style.visibility='hidden';
  var ph=pop.offsetHeight,pw=pop.offsetWidth;
  pop.style.visibility='';
  if(prevHidden){pop.hidden=true;}
  var margin=8;
  var placement=(r.top>=ph+margin)?'above':'below';
  var top=(placement==='above')?(r.top+sy-ph-margin):(r.bottom+sy+margin);
  var left=r.left+sx;
  if(left+pw>sx+window.innerWidth-8){left=sx+window.innerWidth-pw-8;}
  if(left<sx+8){left=sx+8;}
  pop.style.top=top+'px';
  pop.style.left=left+'px';
  pop.setAttribute('data-placement',placement);
}

(function setupInfoPopover(){
  var pop=document.getElementById('trow-info-popover');
  if(!pop)return;
  var openBtn=null;

  function close(){
    if(openBtn){
      try{openBtn.setAttribute('aria-expanded','false');}catch(err){}
    }
    pop.hidden=true;
    openBtn=null;
  }

  function openFor(btn){
    var row=btn.closest?btn.closest('.trow[data-state-summary]'):null;
    if(!row){return;}
    var raw=row.getAttribute('data-state-summary');
    if(!raw){return;}
    var data;
    try{data=JSON.parse(raw);}catch(err){
      if(window.console&&console.warn){console.warn('trow-info-popover: JSON parse failed',err);}
      return;
    }
    pop.innerHTML='';
    pop.appendChild(renderInfoPopoverHtml(data));
    openBtn=btn;
    btn.setAttribute('aria-expanded','true');
    positionPopover(btn,pop);
    pop.hidden=false;
  }

  document.addEventListener('click',function(e){
    var btn=e.target&&e.target.closest?e.target.closest('.info-btn'):null;
    if(btn){
      e.stopPropagation();
      if(openBtn===btn){close();return;}
      if(openBtn){close();}
      openFor(btn);
      return;
    }
    /* Outside click — close if open and click not inside popover */
    if(openBtn){
      var inside=e.target&&e.target.closest?e.target.closest('#trow-info-popover'):null;
      if(!inside){close();}
    }
  },false);

  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'||e.keyCode===27){
      if(openBtn){
        var btn=openBtn;
        close();
        if(btn&&btn.focus){try{btn.focus();}catch(err){}}
      }
    }
  },false);

  window.addEventListener('scroll',function(){if(openBtn){close();}},true);
  window.addEventListener('resize',function(){if(openBtn){close();}},false);
})();"""


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


_ANY_DATA_SECTION_RE = re.compile(r'<\w+[^>]*\bdata-section=', re.IGNORECASE)


def _wrap_with_data_section(section_html: str, key: str) -> str:
    """Inject ``data-section="{key}"`` into the outermost tag of *section_html*.

    Strategy:
    1. If the outermost section/header/aside tag already carries any
       ``data-section="..."`` attribute → return unchanged (``_section_wrap``
       already emits it).
    2. Try regex-based in-place injection on the first ``<section``/``<header``
       tag (one substitution only).
    3. Fallback: wrap with ``<div data-section="{key}">…</div>``.
    """
    # Skip if the outermost tag already declares any data-section attribute.
    if _ANY_DATA_SECTION_RE.search(section_html):
        return section_html

    attr = f'data-section="{key}"'

    # Attempt in-place injection into first <section or <header opening tag.
    match = _DATA_SECTION_TAG_RE.search(section_html)
    if match:
        original_tag = match.group(0)
        # Insert before closing > of the opening tag.
        if original_tag.endswith('/>'):
            new_tag = original_tag[:-2] + f' {attr}/>'
        else:
            new_tag = original_tag[:-1] + f' {attr}>'
        return section_html[:match.start()] + new_tag + section_html[match.end():]

    # Fallback: wrap entire content.
    return f'<div {attr}>{section_html}</div>'


# ---------------------------------------------------------------------------
# Subproject tabs nav section
# ---------------------------------------------------------------------------


def _section_subproject_tabs(model: dict) -> str:
    """Render the subproject tabs nav bar (TSK-01-02).

    Returns an empty string in legacy mode (``is_multi_mode=False``).
    In multi mode returns a ``<nav class="subproject-tabs">`` element with
    ``all`` + one link per subproject.

    Current tab gets ``aria-current="page"`` and ``class="active"``.
    Existing ``lang`` query parameter is preserved in each link.

    Args:
        model: render_state dict with ``is_multi_mode``, ``available_subprojects``,
               ``subproject``, and optionally ``lang`` keys.

    Returns:
        HTML string (empty if legacy mode).
    """
    if not model.get("is_multi_mode"):
        return ""

    current_sp = model.get("subproject") or "all"
    available = model.get("available_subprojects") or []
    lang = model.get("lang") or ""
    lang_qs = f"&lang={_esc(lang)}" if lang and lang != "ko" else ""

    def _tab(sp: str) -> str:
        href = f"?subproject={_esc(sp)}{lang_qs}"
        if sp == current_sp:
            return (
                f'<a href="{href}" class="active" aria-current="page">'
                f'{_esc(sp)}</a>'
            )
        return f'<a href="{href}">{_esc(sp)}</a>'

    tabs = [_tab("all")] + [_tab(sp) for sp in available]
    inner = " | ".join(tabs)
    return f'<nav class="subproject-tabs" data-section="subproject-tabs">{inner}</nav>\n'


def _section_filter_bar(lang: str, distinct_domains: list) -> str:
    """TSK-05-01: Render the sticky filter bar section HTML.

    Renders a ``<div class="filter-bar" data-section="filter-bar" role="search">``
    container with 4 filter controls + reset button:
    - #fb-q: text input (search keyword, case-insensitive)
    - #fb-status: select (running/done/failed/bypass/pending)
    - #fb-domain: select (distinct domains from wbs.md)
    - #fb-model: select (opus/sonnet/haiku)
    - #fb-reset: reset button

    i18n: lang 파라미터 기반 label 텍스트 분기 (ko / en).

    Note: data-section="filter-bar" attribute lets patchSection identify this section,
    but the JS monkey-patch skips filter-bar replacement so filter controls persist.
    """
    lang = _normalize_lang(lang)
    is_ko = lang == "ko"

    q_placeholder   = "🔍 검색 (ID / 제목)" if is_ko else "🔍 Search (ID / title)"
    status_header   = "상태" if is_ko else "Status"
    domain_header   = "도메인" if is_ko else "Domain"
    model_header    = "모델" if is_ko else "Model"
    reset_label     = "✕ 초기화" if is_ko else "✕ Reset"
    reset_aria      = "초기화" if is_ko else "Reset"

    # #fb-status 고정 options
    status_options = "".join([
        f'<option value="">{_esc(status_header)}</option>',
        '<option value="running">running</option>',
        '<option value="done">done</option>',
        '<option value="failed">failed</option>',
        '<option value="bypass">bypass</option>',
        '<option value="pending">pending</option>',
    ])

    # #fb-domain dynamic options from distinct_domains
    domain_options = "".join(
        [f'<option value="">{_esc(domain_header)}</option>']
        + [
            f'<option value="{_esc(str(d))}">{_esc(str(d))}</option>'
            for d in (distinct_domains or [])
        ]
    )

    # #fb-model options
    model_options = "".join([
        f'<option value="">{_esc(model_header)}</option>',
        '<option value="opus">opus</option>',
        '<option value="sonnet">sonnet</option>',
        '<option value="haiku">haiku</option>',
    ])

    return (
        '<div class="filter-bar" data-section="filter-bar" role="search">\n'
        f'  <input id="fb-q" type="search" placeholder="{_esc(q_placeholder)}"'
        '   autocomplete="off" aria-label="Search">\n'
        f'  <select id="fb-status" aria-label="{_esc(status_header)}">'
        f'{status_options}</select>\n'
        f'  <select id="fb-domain" aria-label="{_esc(domain_header)}">'
        f'{domain_options}</select>\n'
        f'  <select id="fb-model" aria-label="{_esc(model_header)}">'
        f'{model_options}</select>\n'
        f'  <button id="fb-reset" type="button" aria-label="{_esc(reset_aria)}">'
        f'{_esc(reset_label)}</button>\n'
        '</div>'
    )


def _build_dashboard_body(s: dict) -> str:
    """Assemble section HTMLs into the ``<body>`` inner content string (v3 layout).

    v3 layout mirrors the reference ``dev-plugin Monitor.html``:
      shell > cmdbar → kpi → grid[ col-left: wp-cards + features,
                                    col-right: activity + team + subagents ]
             → phase-history → dep-graph

    The entire page is wrapped in ``<div class="shell">`` so the cmdbar's
    sticky/backdrop effect aligns with the KPI strip and grid columns.
    """
    wbs_landing_pad = "<a id='wbs' aria-hidden='true' tabindex='-1'></a>\n"
    # subproject-tabs is optional (empty string in legacy mode)
    tabs_html = s.get("subproject-tabs", "")

    # filter-bar — sticky header below tabs, above kpi
    filter_bar_html = s.get("filter-bar", "")

    return "".join([
        '<div class="shell">\n',
        s["header"], "\n",
        tabs_html,
        filter_bar_html, "\n",
        s["kpi"], "\n",
        '  <div class="grid">\n',
        '    <div class="col">\n',
        wbs_landing_pad,
        s["wp-cards"], "\n",
        s["features"], "\n",
        '    </div>\n',
        '    <div class="col">\n',
        s["live-activity"], "\n",
        s["team"], "\n",
        s["subagents"], "\n",
        '    </div>\n',
        '  </div>\n',
        s["phase-history"], "\n",
        s["dep-graph"], "\n",
        '</div>\n',
    ])


def render_dashboard(model: dict, lang: str = "ko", subproject: str = "all") -> str:
    """Render the full v3 monitor dashboard HTML document (TSK-01-06).

    Assembly order (design.md §구현방향):
      sticky_header → kpi → .page[col-left: wp_cards + features,
      col-right: live_activity + team + subagents]
      → phase_history (full-width) → dep-graph (full-width, TSK-03-04)

    Changes from v1:
    - ``<meta http-equiv="refresh">`` removed (JS polling TBD in WP-02).
    - ``.page`` 2-column grid wrapper added.
    - ``data-section="{key}"`` injected on each section for JS partial updates.
    - ``_drawer_skeleton()`` injected before ``</body>``.
    - Empty ``<script id="dashboard-js">`` placeholder inserted for WP-02.
    - ``<a id="wbs">`` landing pad added before wp-cards for backward compat.
    - ``lang`` / ``subproject`` args added (TSK-03-04): dep-graph i18n + SP query.

    TSK-02-02: ``lang`` / ``subproject`` 파라미터 추가.
    - ``lang`` ('ko'|'en', 기본 'ko'): 섹션 h2 heading 번역.
    - ``subproject`` (str): lang-toggle 링크에 보존할 subproject 쿼리 값.
    - ko/en 이외의 lang 값은 'ko'로 정규화한다.

    All user-derived strings flow through ``html.escape`` (via ``_esc``)
    before being concatenated. No external CDN/font/script — only inline CSS.
    The returned string is a complete ``<!DOCTYPE html>`` document.
    """
    if not isinstance(model, dict):
        model = {}

    lang = _normalize_lang(lang)

    # subproject: model에서도 읽을 수 있도록 fallback.
    if not subproject:
        subproject = model.get("subproject", "") or ""

    shared_signals = model.get("shared_signals") or []
    running_ids = _signal_set(shared_signals, "running")
    failed_ids = _signal_set(shared_signals, "failed")

    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []
    panes = model.get("tmux_panes")
    ap_sigs = model.get("agent_pool_signals") or []

    # Defense-in-depth: state.json is source of truth. A task declared terminal
    # ([xx] complete or bypassed) must not render as running/failed even if a
    # stale .running/.failed signal lingers in the shared dir (worker completion
    # path historically wrote `.done` without deleting `.running`). Dashboard
    # rows, WP card counts, and filter chips all consume these sets.
    _terminal_ids = {
        getattr(it, "id", None)
        for it in (list(tasks) + list(features))
        if getattr(it, "id", None)
        and (getattr(it, "status", None) == "[xx]" or getattr(it, "bypassed", False))
    }
    running_ids = running_ids - _terminal_ids
    failed_ids = failed_ids - _terminal_ids

    # Build each section HTML.  ``header`` is excluded from data-section
    # injection (it is nav metadata, not a JS partial-update target).
    # subproject-tabs is also excluded from wrap (it has its own
    # data-section already via _section_subproject_tabs).
    header_html = _section_header(model, lang=lang, subproject=subproject)
    sticky_header_html = (
        '<div data-section="sticky-header">\n'
        f'{_section_sticky_header(model)}\n'
        '</div>'
    )
    tabs_html = _section_subproject_tabs(model)
    # distinct_domains for filter-bar domain select options
    distinct_domains = sorted({
        getattr(t, "domain", None) or ""
        for t in tasks
        if getattr(t, "domain", None)
    })
    filter_bar_html = _section_filter_bar(lang, distinct_domains)
    # docs_dir에서 WP별 merge-status 일괄 로드
    _docs_dir = model.get("docs_dir") or model.get("subproject") or ""
    _wp_merge_state = _load_wp_merge_states(_docs_dir) if _docs_dir else {}
    # wp-progress-spinner: shared_signals에서 WP 레벨 busy 상태 추출
    _wp_busy = _wp_busy_set(shared_signals)
    sections: dict = {
        "kpi":            _section_kpi(model),
        "wp-cards":       _section_wp_cards(tasks, running_ids, failed_ids,
                                            heading=_t(lang, "work_packages"),
                                            wp_titles=model.get("wp_titles") or {},
                                            lang=lang,
                                            wp_merge_state=_wp_merge_state,
                                            wp_busy_set=_wp_busy),
        "features":       _section_features(features, running_ids, failed_ids,
                                            heading=_t(lang, "features"),
                                            lang=lang),
        "live-activity":  _section_live_activity(model,
                                                  heading=_t(lang, "live_activity")),
        "team":           _section_team(panes, heading=_t(lang, "team_agents")),
        "subagents":      _section_subagents(ap_sigs,
                                              heading=_t(lang, "subagents")),
        "dep-graph":      _section_dep_graph(lang=lang, subproject=subproject),
        "phase-history":  _section_phase_history(tasks, features),
    }

    for key in ("kpi", "wp-cards", "features", "team", "subagents", "dep-graph"):
        sections[key] = _wrap_with_data_section(sections[key], key)
    sections["live-activity"] = (
        '<div data-section="live-activity">\n'
        f'{sections["live-activity"]}\n'
        '</div>'
    )
    sections["phase-history"] = (
        '<div data-section="phase-history">\n'
        f'{sections["phase-history"]}\n'
        '  <div data-section="phases" hidden></div>\n'
        '</div>'
    )

    body = _build_dashboard_body({
        **sections,
        "header": header_html,
        "sticky-header": sticky_header_html,
        "subproject-tabs": tabs_html,
        "filter-bar": filter_bar_html,
    })

    css_ver = get_static_version("style.css")
    js_ver = get_static_version("app.js")
    return "".join([
        '<!DOCTYPE html>\n',
        '<html lang="en">\n',
        '<head>\n',
        '  <meta charset="utf-8">\n',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n',
        '  <title>dev-plugin Monitor</title>\n',
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n',
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n',
        '  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">\n',
        f'  <link rel="stylesheet" href="/static/style.css?v={css_ver}">\n',
        f'  <script src="/static/app.js?v={js_ver}" defer></script>\n',
        '</head>\n',
        '<body>\n',
        body, "\n",
        _drawer_skeleton(), "\n",
        _trow_info_popover_skeleton(), "\n",
        _task_panel_dom(), "\n",
        '</body>\n',
        '</html>\n',
    ])


# ---------------------------------------------------------------------------
# Pane capture endpoints (TSK-01-05)
# ---------------------------------------------------------------------------

_PANE_PATH_PREFIX = "/pane/"
_API_PANE_PATH_PREFIX = "/api/pane/"
_DEFAULT_MAX_PANE_LINES = 500

# Inline vanilla JS for 2-second partial refresh of <pre class="pane-capture">.
# No external src — fetch + setInterval are browser built-ins.
_PANE_JS = """\
(function(){
  var pre = document.querySelector('pre.pane-capture');
  var ftr = document.querySelector('.footer');
  if (!pre) return;
  var paneId = pre.getAttribute('data-pane');
  function tick(){
    fetch('/api/pane/' + encodeURIComponent(paneId), {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){
        if (!j) return;
        pre.textContent = (j.lines || []).join('\\n');
        if (ftr) ftr.textContent = 'captured at ' + j.captured_at;
      })
      .catch(function(){ /* silent: loop continues on next tick */ });
  }
  setInterval(tick, 2000);
})();"""

_PANE_CSS = """\
:root {
  --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e; --border: #30363d;
  --panel: #161b22; --accent: #58a6ff; --warn: #f85149;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 1.25rem 1.5rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--fg); line-height: 1.5;
}
h1 { font-size: 1.25rem; margin: 0 0 0.5rem; }
nav.top-nav { margin: 0 0 1rem; padding: 0.25rem 0; border-bottom: 1px solid var(--border); }
nav.top-nav a { color: var(--accent); text-decoration: none; }
nav.top-nav a:hover { text-decoration: underline; }
pre.pane-capture {
  background: #0d1117; border: 1px solid var(--border); border-radius: 4px;
  padding: 0.75rem; margin: 0.5rem 0;
  white-space: pre-wrap; word-break: break-all;
  max-height: 75vh; overflow: auto;
  font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.85rem;
}
.error { color: var(--warn); font-weight: 600; margin: 0.5rem 0; }
.footer { color: var(--muted); font-size: 0.8rem; margin-top: 0.5rem; }"""


# ---------------------------------------------------------------------------
# Static file route helpers (TSK-03-03)
# ---------------------------------------------------------------------------


def _send_plain_404(handler) -> None:
    """Write a minimal ``404 Not Found`` text/plain response to *handler*.

    Shared by :func:`_handle_static` (static-route guard) and
    :meth:`MonitorHandler._route_not_found` to avoid duplicating the same
    response block in multiple places.
    """
    body = b"404 Not Found"
    handler.send_response(404)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _resolve_plugin_root() -> str:
    """Return the plugin root directory path.

    Resolution order:
    1. ``$CLAUDE_PLUGIN_ROOT`` environment variable — set when running inside
       the dev-plugin Claude Code plugin context.
    2. Fallback: parent of the parent of ``__file__`` (i.e., the repository
       root when ``__file__`` is ``scripts/monitor-server.py``).
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if env_val:
        return env_val
    return str(Path(__file__).resolve().parent.parent)


def _is_static_path(path: str) -> bool:
    """Return True iff *path* is a valid /static/{whitelist-file} URL.

    Returns False for:
    - Paths not starting with ``_STATIC_PATH_PREFIX``
    - Paths that contain ``..`` (directory traversal attempt)
    - Filenames not in ``_STATIC_WHITELIST``
    - Empty filename after the prefix

    This function is the *first* defence line — ``_handle_static`` performs a
    second ``Path.resolve()``-based guard as belt-and-suspenders.
    """
    if not isinstance(path, str):
        return False
    if not path.startswith(_STATIC_PATH_PREFIX):
        return False
    if ".." in path:
        return False
    filename = path[len(_STATIC_PATH_PREFIX):]
    if not filename:
        return False
    return filename in _STATIC_WHITELIST


def _handle_static(handler: "BaseHTTPRequestHandler", path: str) -> None:
    """Serve a static vendor JS file to *handler*.

    Protocol:
    - Extract filename from *path* after ``_STATIC_PATH_PREFIX``.
    - Re-validate whitelist + ``..`` guard (second defence line).
    - Resolve absolute path under ``handler.server.plugin_root/skills/dev-monitor/vendor/``.
    - Verify resolved path is still under ``vendor_dir`` (traversal post-resolve).
    - On any failure (whitelist miss, file missing, traversal) → 404.
    - On success → 200 with ``Content-Type: application/javascript; charset=utf-8``
      and ``Cache-Control: public, max-age=3600``.
    """
    # ── Guard 1: prefix + traversal + whitelist ──────────────────────────────
    if not isinstance(path, str) or not path.startswith(_STATIC_PATH_PREFIX):
        _send_plain_404(handler)
        return
    if ".." in path:
        _send_plain_404(handler)
        return
    filename = path[len(_STATIC_PATH_PREFIX):]
    if not filename or filename not in _STATIC_WHITELIST:
        _send_plain_404(handler)
        return

    # ── Resolve vendor directory via plugin_root ──────────────────────────────
    plugin_root = _server_attr(handler, "plugin_root") or _resolve_plugin_root()
    vendor_dir = Path(plugin_root) / "skills" / "dev-monitor" / "vendor"
    target = vendor_dir / filename

    # ── Guard 2: post-resolve traversal check ────────────────────────────────
    try:
        resolved = target.resolve()
        vendor_resolved = vendor_dir.resolve()
        # resolved must be vendor_dir itself or a direct child
        if vendor_resolved not in (resolved, *resolved.parents):
            _send_plain_404(handler)
            return
    except (OSError, ValueError):
        _send_plain_404(handler)
        return

    # ── File read ────────────────────────────────────────────────────────────
    try:
        data = target.read_bytes()
    except OSError:
        _send_plain_404(handler)
        return

    # ── Successful response ───────────────────────────────────────────────────
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "public, max-age=3600")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _is_pane_html_path(path: str) -> bool:
    """Return True iff *path* starts with ``/pane/`` but NOT ``/api/pane/``."""
    if not isinstance(path, str):
        return False
    return path.startswith(_PANE_PATH_PREFIX) and not path.startswith(_API_PANE_PATH_PREFIX)


def _is_pane_api_path(path: str) -> bool:
    """Return True iff *path* starts with ``/api/pane/``."""
    if not isinstance(path, str):
        return False
    return path.startswith(_API_PANE_PATH_PREFIX)


def _extract_pane_id(path: str, prefix: str) -> str:
    """Strip *prefix* from *path* and URL-decode the remainder.

    Returns the decoded pane_id string (may be empty — callers must validate
    against ``_PANE_ID_RE``).
    """
    return unquote(path[len(prefix):])


def _pane_capture_payload(
    pane_id: str,
    capture: Callable[[str], str],
    max_lines: int = _DEFAULT_MAX_PANE_LINES,
) -> dict:
    """Build the shared payload dict for both HTML and JSON pane endpoints.

    Validation: ``^%\\d+$`` regex. Raises ``ValueError`` on format violation so the
    HTTP layer can map to 400 without ever spawning a subprocess.

    On subprocess failure the returned dict has ``error`` populated and ``lines``
    contains a single error message line. HTTP status stays 200 (acceptance §1).
    On success ``error`` is ``None``.

    Truncation: the *last* ``max_lines`` lines are kept; ``truncated_from`` holds
    the original line count before truncation.
    """
    if not isinstance(pane_id, str) or not _PANE_ID_RE.fullmatch(pane_id):
        raise ValueError(f"invalid pane id: {pane_id!r}")

    error: Optional[str] = None
    try:
        raw_text = capture(pane_id)
    except FileNotFoundError:
        error = "tmux not available"
        raw_text = f"capture failed: {error}"
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        raw_text = f"capture failed: {error}"

    all_lines = raw_text.splitlines()
    original_count = len(all_lines)
    lines = all_lines[-max_lines:] if original_count > max_lines else all_lines

    captured_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    return {
        "pane_id": pane_id,
        "captured_at": captured_at,
        "lines": lines,
        "line_count": len(lines),
        "truncated_from": original_count,
        "error": error,
    }


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


def _send_html_response(handler, status: int, body_str: str) -> None:
    """Write a text/html; charset=utf-8 response to *handler*.

    monitor-perf (2026-04-24): 200 응답에 weak-ETag를 붙이고 If-None-Match가
    일치하면 304 (본문 0바이트)로 단축. 대시보드 SSR(75KB+)을 5초마다 폴링하는
    시나리오에서 변화 없으면 body 전송·DOMParser·patchSection 모두 스킵.
    """
    body = body_str.encode("utf-8")
    # 200 응답에만 ETag 적용 (4xx/5xx는 원본 동작 유지)
    if status == 200:
        _ensure_etag_cache()
        if _compute_etag is not None and _check_if_none_match is not None:
            etag = _compute_etag(body)
            if _check_if_none_match(handler, etag):
                handler.send_response(304)
                handler.send_header("ETag", etag)
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                return
            handler.send_response(200)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("ETag", etag)
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(body)
            return
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


# _handle_pane_html, _handle_pane_api: moved to handlers_pane.py [core-http-split:refactor-01]
# facade re-export via try/except block at bottom of this file.


# ---------------------------------------------------------------------------
# /api/graph endpoint (TSK-03-02)
# ---------------------------------------------------------------------------

_API_GRAPH_PATH = "/api/graph"
_DEP_ANALYSIS_TIMEOUT = 3  # seconds

# Active statuses that map to "running" (no signal needed)
_RUNNING_STATUSES = {"[dd]", "[im]", "[ts]"}

# Number of phase_history entries to include in /api/graph node payload.
# Distinct from server-internal _PHASE_TAIL_LIMIT=10 (used for dashboard history table).
_GRAPH_PHASE_TAIL_LIMIT = 3


# _serialize_phase_history_tail_for_graph: moved to monitor_server.api (C0-4).


def _is_api_graph_path(path: str) -> bool:
    """Return True iff *path* matches ``/api/graph`` exactly (query allowed).

    - ``"/api/graph"`` → True
    - ``"/api/graph?subproject=all"`` → True
    - ``"/api/graph/"`` → False (trailing slash)
    - ``"/api/graphql"`` → False

    Matching uses :func:`urllib.parse.urlsplit` so the query string is stripped
    before the equality comparison.
    """
    if not isinstance(path, str):
        return False
    return urlsplit(path).path == _API_GRAPH_PATH


# _derive_node_status: moved to monitor_server.api (C0-4).


# _build_graph_payload: moved to monitor_server.api (C0-4).


_DEP_ANALYSIS_MODULE_NAME = "dep_analysis_inproc"


def _load_dep_analysis_module():
    """Load dep-analysis.py in-process via importlib, returning the module.

    Uses ``sys.modules`` cache with key ``_DEP_ANALYSIS_MODULE_NAME`` to avoid
    repeated loading. Falls back to None on import failure.

    The module is loaded from ``scripts/dep-analysis.py`` — one directory above
    the ``monitor_server/`` package. The file name uses a hyphen which is not a
    valid Python identifier, so ``importlib.util.spec_from_file_location`` is
    required.
    """
    import importlib.util as _ilu

    cached = sys.modules.get(_DEP_ANALYSIS_MODULE_NAME)
    if cached is not None:
        return cached

    # dep-analysis.py sits in scripts/, which is the *parent* of this package dir.
    scripts_dir = Path(__file__).resolve().parent.parent
    dep_analysis_path = scripts_dir / "dep-analysis.py"
    if not dep_analysis_path.exists():
        return None
    try:
        spec = _ilu.spec_from_file_location(_DEP_ANALYSIS_MODULE_NAME, dep_analysis_path)
        if spec is None:
            return None
        mod = _ilu.module_from_spec(spec)
        sys.modules[_DEP_ANALYSIS_MODULE_NAME] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        sys.modules.pop(_DEP_ANALYSIS_MODULE_NAME, None)
        return None


def _call_dep_analysis_graph_stats(tasks_input: list) -> "Tuple[Optional[dict], str]":
    """Compute graph stats for *tasks_input* via in-process importlib import.

    Returns ``(graph_stats_dict, "")`` on success, or ``(None, error_message)``
    on failure.

    Primary path: import dep-analysis.py in-process and call
    ``compute_graph_stats(tasks_input)`` directly — zero subprocess forks.

    Fallback: if the module cannot be loaded, falls back to subprocess (degraded
    mode). The fallback path uses the correct scripts/ directory for the script
    path, unlike the previous implementation that pointed to monitor_server/.
    """
    # --- Primary: in-process importlib ---
    dep_mod = _load_dep_analysis_module()
    if dep_mod is not None:
        fn = getattr(dep_mod, "compute_graph_stats", None)
        if fn is not None:
            try:
                result = fn(tasks_input)
                return result, ""
            except ValueError as exc:
                return None, f"dep-analysis compute error: {exc!r}"
            except Exception as exc:
                return None, f"dep-analysis unexpected error: {exc!r}"

    # --- Fallback: subprocess (degraded mode) ---
    scripts_dir = Path(__file__).resolve().parent.parent
    dep_analysis_script = str(scripts_dir / "dep-analysis.py")
    try:
        proc = subprocess.run(
            [sys.executable, dep_analysis_script, "--graph-stats"],
            input=json.dumps(tasks_input, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=_DEP_ANALYSIS_TIMEOUT,
            check=False,
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as exc:
        return None, f"dep-analysis error: {exc!r}"

    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or "").strip()[:200]
        return None, f"dep-analysis exited {proc.returncode}: {stderr_snippet}"

    try:
        return json.loads(proc.stdout), ""
    except (ValueError, TypeError) as exc:
        return None, f"dep-analysis bad JSON: {exc!r}"


# _build_fan_in_map: moved to monitor_server.api (C0-4).


def _graph_etag(json_bytes: bytes) -> str:
    """Compute a quoted ETag string from JSON bytes using sha256[:12]."""
    digest = hashlib.sha256(json_bytes).hexdigest()[:12]
    return f'"{digest}"'


def _get_if_none_match(handler) -> str:
    """Extract If-None-Match header value from a request handler.

    Handles both dict-like (test mocks) and http.server headers (bytes key).
    Returns empty string if absent.
    """
    headers = getattr(handler, "headers", None)
    if headers is None:
        return ""
    # MagicMock / plain dict: try string key first
    try:
        val = headers.get("If-None-Match", "") or headers.get(b"If-None-Match", b"") or ""
        if isinstance(val, bytes):
            val = val.decode("utf-8", errors="replace")
        return str(val)
    except Exception:
        return ""


# _handle_graph_api: moved to handlers_graph.py [core-http-split:refactor-01]
# facade re-export via try/except block at bottom of this file.


# /api/state JSON snapshot endpoint (TSK-01-06)
# ---------------------------------------------------------------------------

_API_STATE_PATH = "/api/state"


def _is_api_state_path(path: str) -> bool:
    """Return True iff *path* matches ``/api/state`` exactly (query allowed).

    - ``"/api/state"`` → True
    - ``"/api/state?pretty=1"`` → True
    - ``"/api/state/"`` → False (trailing slash is not the same route)
    - ``"/api/statey"`` / ``"/api/pane/%1"`` / ``"/"`` → False

    Matching uses :func:`urllib.parse.urlsplit` so the query string is stripped
    before the equality comparison.
    """
    if not isinstance(path, str):
        return False
    return urlsplit(path).path == _API_STATE_PATH


# ---------------------------------------------------------------------------
# /api/task-detail endpoint (TSK-02-04)
# ---------------------------------------------------------------------------

_API_TASK_DETAIL_PATH = "/api/task-detail"

_WBS_SECTION_RE = re.compile(r"^### (?P<id>TSK-\S+):", re.MULTILINE)
_TSK_ID_VALID_RE = re.compile(r"^TSK-\S+$")
# Mirrors feat-init.py's FEAT_NAME_RE — only kebab-case lowercase names are valid.
_FEAT_ID_VALID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _is_api_task_detail_path(path: str) -> bool:
    """Return True iff path matches /api/task-detail exactly (query allowed)."""
    if not isinstance(path, str):
        return False
    return urlsplit(path).path == _API_TASK_DETAIL_PATH


def _extract_wbs_section(wbs_md: str, task_id: str) -> str:
    """Extract WBS section for task_id from wbs_md. Returns stripped text or ''.

    Sections are bounded by the next ``### `` or ``## `` header, whichever comes first.
    """
    matches = list(_WBS_SECTION_RE.finditer(wbs_md))
    for i, m in enumerate(matches):
        if m.group("id") != task_id:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wbs_md)
        h2_match = re.search(r"^## ", wbs_md[start:end], re.MULTILINE)
        if h2_match:
            end = start + h2_match.start()
        return wbs_md[start:end].strip()
    return ""


# Log file names to tail for the EXPAND panel § 로그 section (TSK-02-06).
LOG_NAMES = ("build-report.md", "test-report.md")

_MAX_LOG_TAIL_LINES = 200


def _tail_report(path, max_lines=_MAX_LOG_TAIL_LINES) -> dict:
    """Return tail dict for a single log file.

    Schema: {name, tail, truncated, lines_total, exists}.
    - File missing → exists=False, tail='', lines_total=0, truncated=False.
    - ANSI CSI escapes are stripped via _ANSI_RE.
    - UTF-8 decode errors are replaced (never raises).
    """
    name = Path(path).name
    if not Path(path).exists():
        return {"name": name, "tail": "", "truncated": False, "lines_total": 0, "exists": False}
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"name": name, "tail": "", "truncated": False, "lines_total": 0, "exists": False}
    raw = _ANSI_RE.sub("", raw)
    all_lines = raw.splitlines()
    lines_total = len(all_lines)
    truncated = lines_total > max_lines
    tail_lines = all_lines[-max_lines:] if truncated else all_lines
    tail = "\n".join(tail_lines)
    return {
        "name": name,
        "tail": tail,
        "truncated": truncated,
        "lines_total": lines_total,
        "exists": True,
    }


def _collect_logs(task_dir) -> list:
    """Return [{name, tail, truncated, lines_total, exists}] for LOG_NAMES."""
    return [_tail_report(Path(task_dir) / name) for name in LOG_NAMES]


def _collect_artifacts(task_dir, artifact_names=("design.md", "test-report.md", "refactor.md")):
    """Return [{name, path, exists, size}] for the given artifact names."""
    result = []
    for name in artifact_names:
        filepath = task_dir / name
        try:
            st = filepath.stat()
            exists = True
            size = st.st_size
        except OSError:
            exists = False
            size = 0
        raw = str(task_dir / name)
        docs_idx = raw.find("docs/")
        rel = raw[docs_idx:] if docs_idx >= 0 else raw
        result.append({"name": name, "path": rel, "exists": exists, "size": size})
    return result


_FEAT_ARTIFACT_NAMES = ("spec.md", "design.md", "test-report.md", "refactor.md")


def _collect_feat_artifacts(feat_dir):
    """Return [{name, path, exists, size}] for Feature artifacts (includes spec.md)."""
    return _collect_artifacts(feat_dir, _FEAT_ARTIFACT_NAMES)


def _extract_title_from_section(section_md: str) -> str:
    """Extract task title from the first line of a WBS section.

    Example: ``### TSK-02-04: Some Title`` → ``"Some Title"``.
    Returns empty string when the pattern is not found.
    """
    first_line = section_md.splitlines()[0] if section_md else ""
    tsk_pos = first_line.find("TSK-")
    if tsk_pos < 0:
        return ""
    colon_pos = first_line.find(":", tsk_pos)
    if colon_pos < 0:
        return ""
    return first_line[colon_pos + 1:].strip()


def _extract_wp_id(section_md: str, wbs_md: str, task_id: str) -> str:
    """Resolve wp_id for a task.

    Priority: (1) ``- wp:`` metadata line inside the section,
    (2) reverse-scan of wbs_md for the nearest ``## WP-*:`` header before the section.
    Returns empty string when neither is found.
    """
    for line in section_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("- wp:"):
            return stripped[len("- wp:"):].strip()
    section_start = wbs_md.find(f"### {task_id}:")
    if section_start > 0:
        preceding = wbs_md[:section_start]
        wp_match = None
        for m in re.finditer(r"^## (WP-\S+)", preceding, re.MULTILINE):
            wp_match = m
        if wp_match:
            return wp_match.group(1).rstrip(":")
    return ""


# _load_state_json, _build_task_detail_payload: moved to monitor_server.api (C0-4).


# _handle_api_task_detail: moved to handlers_graph.py [core-http-split:refactor-01]
# facade re-export via try/except block at bottom of this file.


# ---------------------------------------------------------------------------
# /api/merge-status endpoint (TSK-04-02)
# ---------------------------------------------------------------------------

_API_MERGE_STATUS_PATH = "/api/merge-status"
_MERGE_STATUS_FILENAME = "merge-status.json"
_MERGE_STALE_SECONDS = 1800


def _is_api_merge_status_path(path: str) -> bool:
    """Return True iff path matches /api/merge-status exactly (query allowed)."""
    if not isinstance(path, str):
        return False
    return urlsplit(path).path == _API_MERGE_STATUS_PATH


def _badge_label_for_state(state: str) -> str:
    """Return a human-readable badge label for a merge state."""
    return {
        "ready": "\U0001f7e2 머지 가능",
        "waiting": "\U0001f7e1 대기 중",
        "conflict": "\U0001f534 충돌",
    }.get(state, "⚫ 알 수 없음")


def _load_merge_status_file(path: "Path") -> "Optional[dict]":
    """Load and return a merge-status.json file. Returns None on error."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None


def _is_merge_status_stale(path: "Path", data: dict) -> bool:
    """Compute is_stale from file mtime. Falls back to data field on OSError."""
    try:
        return (time.time() - path.stat().st_mtime) > _MERGE_STALE_SECONDS
    except OSError:
        return data.get("is_stale", False)


def _load_merge_status(docs_dir: str, wp_id: "Optional[str]") -> "tuple[object, int]":
    """Load merge-status.json for a single WP or all WPs.

    Returns (payload, status_code).
    - wp_id=None: returns list of summary dicts (conflicts excluded)
    - wp_id specified: returns full dict including conflicts, or ({}, 404) if missing
    """
    wp_state_dir = Path(docs_dir) / "wp-state"

    if wp_id:
        # Single WP detail
        status_file = wp_state_dir / wp_id / _MERGE_STATUS_FILENAME
        if not status_file.exists():
            return ({}, 404)
        data = _load_merge_status_file(status_file)
        if data is None:
            return ({}, 404)
        # Recalculate is_stale from file mtime (consistent after server restarts)
        data["is_stale"] = _is_merge_status_stale(status_file, data)
        return (data, 200)
    else:
        # All WPs summary (no conflicts array)
        summary = []
        if not wp_state_dir.exists():
            return (summary, 200)
        try:
            entries = list(wp_state_dir.iterdir())
        except OSError:
            return (summary, 200)
        for entry in sorted(entries):
            if not entry.is_dir():
                continue
            status_file = entry / _MERGE_STATUS_FILENAME
            if not status_file.exists():
                continue
            data = _load_merge_status_file(status_file)
            if data is None:
                continue
            # Summary: exclude full conflicts array
            row = {
                "wp_id": data.get("wp_id", entry.name),
                "state": data.get("state", "unknown"),
                "pending_count": data.get("pending_count", 0),
                "conflict_count": data.get("conflict_count", 0),
                "is_stale": _is_merge_status_stale(status_file, data),
            }
            summary.append(row)
        return (summary, 200)


def _collect_merge_summary(docs_dir: str) -> dict:
    """Collect WP merge state summaries for /api/state bundle.

    Returns {wp_id: {state, badge_label, pending_count, conflict_count, is_stale}}.
    Does NOT include full conflicts array.
    """
    wp_state_dir = Path(docs_dir) / "wp-state"
    result = {}
    if not wp_state_dir.exists():
        return result
    try:
        entries = list(wp_state_dir.iterdir())
    except OSError:
        return result
    for entry in entries:
        if not entry.is_dir():
            continue
        status_file = entry / _MERGE_STATUS_FILENAME
        if not status_file.exists():
            continue
        data = _load_merge_status_file(status_file)
        if data is None:
            continue
        state = data.get("state", "unknown")
        wp = data.get("wp_id", entry.name)
        result[wp] = {
            "state": state,
            "badge_label": _badge_label_for_state(state),
            "pending_count": data.get("pending_count", 0),
            "conflict_count": data.get("conflict_count", 0),
            "is_stale": _is_merge_status_stale(status_file, data),
        }
    return result


def _handle_api_merge_status(handler) -> None:
    """Handle GET /api/merge-status."""
    try:
        raw_path = getattr(handler, "path", "") or ""
        qs = urlsplit(raw_path).query
        qp = parse_qs(qs, keep_blank_values=False)
        raw_sp = (qp.get("subproject") or ["all"])[0] or "all"
        wp_param: "Optional[str]" = (qp.get("wp") or [None])[0] or None

        base_docs_dir = _server_attr(handler, "docs_dir")
        available_subprojects = discover_subprojects(base_docs_dir)
        if raw_sp != "all" and raw_sp not in available_subprojects:
            raw_sp = "all"
        effective_docs_dir = _resolve_effective_docs_dir(base_docs_dir, raw_sp)

        payload, status_code = _load_merge_status(effective_docs_dir, wp_param)

        if status_code == 404:
            _json_error(handler, 404, f"WP not found: {wp_param!r}")
            return

        _json_response(handler, status_code, payload)
    except Exception as exc:
        sys.stderr.write(f"/api/merge-status error: {exc!r}\n")
        _json_error(handler, 500, str(exc))


def _task_panel_css() -> str:
    """CSS for task slide panel (TSK-02-04)."""
    return (
        ".slide-panel{--panel-w:clamp(320px,800px,95vw);--panel-header-h:56px;"
        "position:fixed;top:0;right:calc(var(--panel-w) * -1);bottom:0;width:var(--panel-w);"
        "background:var(--bg-2,#1e1e2e);border-left:1px solid var(--border,#313244);"
        "overflow-y:auto;z-index:90;transition:right 0.22s cubic-bezier(.4,0,.2,1);"
        "display:flex;flex-direction:column;}"
        ".slide-panel.open{right:0;}"
        ".slide-panel.resizing{transition:none;}"
        ".slide-panel-resize-handle{position:absolute;top:0;bottom:0;left:0;width:6px;"
        "cursor:ew-resize;background:transparent;z-index:91;touch-action:none;}"
        ".slide-panel-resize-handle:hover,.slide-panel-resize-handle.dragging{"
        "background:var(--accent,#58a6ff);opacity:0.45;}"
        "#task-panel-overlay{position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:80;}"
        "#task-panel > header{display:flex;align-items:center;justify-content:space-between;"
        "padding:0 16px;height:var(--panel-header-h);border-bottom:1px solid var(--border,#313244);"
        "position:sticky;top:0;z-index:21;background:var(--bg-2,#1e1e2e);flex-shrink:0;}"
        "#task-panel-body{padding:16px;}"
        "#task-panel-close{background:none;border:none;cursor:pointer;font-size:18px;"
        "color:var(--ink-3,#cdd6f4);opacity:.7;line-height:1;}"
        "#task-panel-close:hover{opacity:1;}"
        "#task-panel-body h4{margin:16px 0 8px;font-size:13px;color:var(--ink-3,#cdd6f4);}"
        "#task-panel-body pre{background:var(--bg-1,#181825);border-radius:4px;padding:10px;"
        "overflow-x:auto;font-size:12px;white-space:pre-wrap;word-break:break-word;}"
        "#task-panel-body .disabled{color:var(--ink-3,#585b70);}"
        "#task-panel-body .size{font-size:11px;color:var(--ink-3,#585b70);margin-left:6px;}"
        "#task-panel-body ul{list-style:none;padding:0;margin:0;}"
        "#task-panel-body li{padding:4px 0;font-size:12px;}"
        ".expand-btn{font-size:14px;padding:2px 6px;opacity:.5;background:none;"
        "border:none;cursor:pointer;color:inherit;}"
        ".expand-btn:hover{opacity:1;}"
        "#task-panel-body code{font-family:var(--font-mono,monospace);font-size:12px;}"
        ".panel-logs{margin-top:4px;}"
        ".log-entry{margin-bottom:8px;}"
        ".log-entry summary{cursor:pointer;font-size:12px;color:var(--ink-3,#cdd6f4);padding:2px 0;user-select:none;}"
        ".log-tail{max-height:300px;overflow:auto;font-size:11px;white-space:pre-wrap;"
        "word-break:break-all;background:var(--bg-1,#181825);border-radius:4px;"
        "padding:8px;margin:4px 0 0;font-family:var(--font-mono,monospace);}"
        ".log-empty{font-size:12px;color:var(--ink-3,#585b70);padding:4px 0;}"
        ".log-trunc{font-size:10px;color:var(--ink-3,#585b70);margin-left:8px;}"
        # merge-badge + merge preview panel CSS
        ".merge-badge{display:inline-flex;align-items:center;gap:4px;"
        "padding:2px 8px;border-radius:12px;cursor:pointer;"
        "font-size:11px;font-weight:600;border:1px solid transparent;"
        "flex-shrink:0;white-space:nowrap;background:none;}"
        ".merge-badge[data-state=\"ready\"]{background:var(--done,#22c55e20);color:var(--done,#22c55e);border-color:var(--done,#22c55e);}"
        ".merge-badge[data-state=\"waiting\"]{background:var(--run,#eab30820);color:var(--run,#eab308);border-color:var(--run,#eab308);}"
        ".merge-badge[data-state=\"conflict\"]{background:var(--fail,#ef444420);color:var(--fail,#ef4444);border-color:var(--fail,#ef4444);}"
        ".merge-badge[data-state=\"stale\"]{background:transparent;color:var(--ink-3,#cdd6f4);border:1px dashed var(--ink-3,#cdd6f4);}"
        ".merge-badge[data-state=\"unknown\"]{background:transparent;color:var(--ink-3,#585b70);border-color:var(--ink-3,#585b70);}"
        ".merge-badge .stale{font-size:10px;opacity:.8;}"
        ".merge-stale-banner{padding:6px 10px;background:var(--run,#eab30820);border:1px solid var(--run,#eab308);border-radius:4px;font-size:12px;margin-bottom:12px;}"
        ".merge-ready-banner{padding:6px 10px;background:var(--done,#22c55e20);border:1px solid var(--done,#22c55e);border-radius:4px;font-size:12px;margin-bottom:12px;}"
        ".merge-conflict-file li.disabled{color:var(--ink-3,#585b70);}"
        ".merge-conflict-file li.disabled code{opacity:.6;}"
        ".merge-hunk-preview{max-height:120px;overflow:auto;font-size:11px;font-family:var(--font-mono,monospace);background:var(--bg-1,#181825);border-radius:4px;padding:6px;white-space:pre-wrap;word-break:break-all;margin-top:4px;}"
        # EXPAND 패널 sticky progress header
        ".progress-header{position:sticky;top:var(--panel-header-h,56px);z-index:20;"
        "background:var(--bg-2,#1e1e2e);"
        "border-bottom:1px solid var(--border,#313244);"
        "margin:-16px -16px 12px;padding:10px 16px;"
        "display:flex;flex-direction:column;gap:6px;}"
        ".progress-header .ph-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}"
        ".ph-badge{display:inline-flex;align-items:center;gap:4px;"
        "padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;"
        "border:1px solid transparent;white-space:nowrap;}"
        ".ph-badge[data-phase=\"dd\"]{background:rgba(56,139,253,0.15);color:#4aa3ff;border-color:rgba(56,139,253,0.4);}"
        ".ph-badge[data-phase=\"im\"]{background:rgba(188,140,255,0.15);color:#bc8cff;border-color:rgba(188,140,255,0.4);}"
        ".ph-badge[data-phase=\"ts\"]{background:rgba(63,185,80,0.15);color:var(--done,#22c55e);border-color:rgba(63,185,80,0.4);}"
        ".ph-badge[data-phase=\"xx\"]{background:rgba(139,148,158,0.15);color:var(--ink-3,#cdd6f4);border-color:rgba(139,148,158,0.4);}"
        ".ph-badge[data-phase=\"pending\"]{background:transparent;color:var(--ink-3,#585b70);border-color:var(--ink-3,#585b70);}"
        ".ph-badge[data-running=\"true\"] .spinner{display:inline-block;}"
        ".ph-meta{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;"
        "margin:0;font-size:11px;color:var(--ink-3,#cdd6f4);}"
        ".ph-meta dt{opacity:.7;}"
        ".ph-meta dd{margin:0;font-family:var(--font-mono,monospace);}"
        ".ph-history{list-style:none;padding:0;margin:4px 0 0;"
        "font-size:11px;color:var(--ink-3,#cdd6f4);}"
        ".ph-history li{padding:2px 0;display:flex;gap:8px;"
        "font-family:var(--font-mono,monospace);}"
        ".ph-history li .ph-time{opacity:.6;min-width:140px;}"
        ".ph-history-empty{font-size:11px;color:var(--ink-3,#585b70);font-style:italic;}"
        # state.json 표 형태 렌더링
        ".state-empty{font-size:12px;color:var(--ink-3,#585b70);font-style:italic;}"
        ".state-table,.state-history-table{width:100%;border-collapse:collapse;"
        "font-size:12px;font-family:var(--font-mono,monospace);margin:4px 0 8px;}"
        ".state-table th,.state-table td,"
        ".state-history-table th,.state-history-table td{"
        "padding:4px 8px;border-bottom:1px solid var(--border,#313244);"
        "text-align:left;vertical-align:top;}"
        ".state-table th{width:140px;color:var(--ink-3,#cdd6f4);opacity:.75;"
        "font-weight:500;white-space:nowrap;}"
        ".state-table td{color:var(--ink-3,#cdd6f4);word-break:break-all;}"
        ".state-history-table thead th{color:var(--ink-3,#cdd6f4);opacity:.75;"
        "font-weight:500;font-size:11px;text-transform:uppercase;"
        "letter-spacing:.04em;background:var(--bg-1,#181825);}"
        ".state-history-table td{color:var(--ink-3,#cdd6f4);}"
        ".state-history-table td.state-idx{color:var(--ink-3,#585b70);"
        "width:28px;text-align:right;}"
        ".state-subhead{margin:12px 0 4px;font-size:12px;opacity:.7;"
        "color:var(--ink-3,#cdd6f4);}"
    )


_TASK_PANEL_JS = r"""
function escapeHtml(s){
  if(s==null)return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function renderWbsSection(md,source){
  if(!md)return '';
  var heading=(source==='feat')?'&sect; 사양':'&sect; WBS';
  var lines=md.split('\n'),html='<h4>'+heading+'</h4>',inCode=false,lang='';
  for(var i=0;i<lines.length;i++){
    var line=lines[i];
    if(!inCode&&line.match(/^```/)){inCode=true;lang=line.slice(3).trim();html+='<pre><code'+(lang?' class="lang-'+escapeHtml(lang)+'"':'')+'>';continue;}
    if(inCode){if(line.match(/^```/)){inCode=false;html+='</code></pre>\n';}else{html+=escapeHtml(line)+'\n';}continue;}
    var m4=line.match(/^####\s+(.*)/),m3=line.match(/^###\s+(.*)/),m2=line.match(/^##\s+(.*)/),m1=line.match(/^#\s+(.*)/);
    if(m4){html+='<h5>'+escapeHtml(m4[1])+'</h5>\n';continue;}
    if(m3){html+='<h4>'+escapeHtml(m3[1])+'</h4>\n';continue;}
    if(m2){html+='<h3>'+escapeHtml(m2[1])+'</h3>\n';continue;}
    if(m1){html+='<h2>'+escapeHtml(m1[1])+'</h2>\n';continue;}
    var li=line.match(/^\s*[-*]\s+(.*)/);
    if(li){html+='<li>'+escapeHtml(li[1])+'</li>\n';continue;}
    if(line.trim()===''){html+='<br>\n';continue;}
    html+='<p>'+escapeHtml(line)+'</p>\n';
  }
  if(inCode)html+='</code></pre>\n';
  return html;
}
function renderTaskProgressHeader(state){
  if(!state)return '';
  var status=state.status||'[ ]';
  var phase=String(status).replace('[','').replace(']','').trim();
  if(!phase||phase===' ')phase='pending';
  var last=state.last||{};
  var evt=last.event||'';
  var isRunning=/_(start|running)$/.test(evt);
  var elapsed=state.elapsed_seconds;
  var elapsedStr=(elapsed==null)?'-':String(elapsed)+'s';
  var lastAt=last.at||'-';
  var history=state.phase_history||[];
  var historyLen=history.length;
  var spinner=isRunning?'<span class="spinner"></span>':'';
  var html='<header class="progress-header">';
  html+='<div class="ph-row">';
  html+='<span class="ph-badge" data-phase="'+escapeHtml(phase)+'"'
    +(isRunning?' data-running="true"':'')+'>'
    +escapeHtml(phase)+spinner+'</span>';
  html+='<span class="ph-last-event">'+escapeHtml(evt||'-')+'</span>';
  html+='</div>';
  html+='<dl class="ph-meta">'
    +'<dt>status</dt><dd>'+escapeHtml(status)+'</dd>'
    +'<dt>last.at</dt><dd>'+escapeHtml(lastAt)+'</dd>'
    +'<dt>elapsed</dt><dd>'+escapeHtml(elapsedStr)+'</dd>'
    +'<dt>phaseCount</dt><dd>'+escapeHtml(String(historyLen))+'</dd>'
    +'</dl>';
  if(historyLen===0){
    html+='<div class="ph-history-empty">phase_history 없음</div>';
  }else{
    var recent=history.slice(-3).reverse();
    html+='<ul class="ph-history">';
    for(var i=0;i<recent.length;i++){
      var h=recent[i]||{};
      html+='<li><span class="ph-time">'+escapeHtml(h.at||'-')+'</span>'
        +'<span class="ph-evt">'+escapeHtml(h.event||'-')+'</span></li>';
    }
    html+='</ul>';
  }
  html+='</header>';
  return html;
}
function _fmtElapsedSec(sec){
  if(sec==null||sec==='')return '—';
  var n=Number(sec);
  if(!isFinite(n))return String(sec);
  if(n<60)return n+'s';
  var m=Math.floor(n/60),s=n%60;
  return m+'m '+s+'s';
}
function _fmtStateVal(v){
  if(v==null||v==='')return '—';
  if(typeof v==='boolean')return v?'true':'false';
  return String(v);
}
function renderStateJson(state){
  var html='<h4>&sect; state.json</h4>';
  if(!state||typeof state!=='object'||Object.keys(state).length===0){
    return html+'<p class="state-empty">데이터 없음</p>';
  }
  var rows=[];
  var last=(state.last&&typeof state.last==='object')?state.last:null;
  if('name' in state)rows.push(['name',_fmtStateVal(state.name)]);
  rows.push(['status',_fmtStateVal(state.status)]);
  if('started_at' in state)rows.push(['started_at',_fmtStateVal(state.started_at)]);
  if(last){
    rows.push(['last.event',_fmtStateVal(last.event)]);
    rows.push(['last.at',_fmtStateVal(last.at)]);
  }
  if('updated' in state)rows.push(['updated',_fmtStateVal(state.updated)]);
  if('completed_at' in state)rows.push(['completed_at',_fmtStateVal(state.completed_at)]);
  if('elapsed_seconds' in state)rows.push(['elapsed',_fmtElapsedSec(state.elapsed_seconds)]);
  if(state.bypassed)rows.push(['bypassed','true']);
  if(state.bypassed_reason)rows.push(['bypassed_reason',_fmtStateVal(state.bypassed_reason)]);
  html+='<table class="state-table"><tbody>';
  for(var i=0;i<rows.length;i++){
    html+='<tr><th>'+escapeHtml(rows[i][0])+'</th><td>'+escapeHtml(rows[i][1])+'</td></tr>';
  }
  html+='</tbody></table>';
  var history=(state.phase_history&&state.phase_history.length)?state.phase_history:null;
  if(history){
    html+='<h5 class="state-subhead">phase_history ('+history.length+')</h5>';
    html+='<table class="state-history-table"><thead><tr>'
      +'<th>#</th><th>event</th><th>from</th><th>to</th><th>at</th><th>elapsed</th>'
      +'</tr></thead><tbody>';
    for(var j=0;j<history.length;j++){
      var h=history[j]||{};
      html+='<tr>'
        +'<td class="state-idx">'+(j+1)+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.event))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.from))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.to))+'</td>'
        +'<td>'+escapeHtml(_fmtStateVal(h.at))+'</td>'
        +'<td>'+escapeHtml(_fmtElapsedSec(h.elapsed_seconds))+'</td>'
        +'</tr>';
    }
    html+='</tbody></table>';
  }
  return html;
}
function renderArtifacts(arts){
  var html='<h4>&sect; 아티팩트</h4>';
  if(!arts||!arts.length)return html+'<p>-</p>';
  html+='<ul>';
  for(var i=0;i<arts.length;i++){
    var a=arts[i];
    if(a.exists)html+='<li><code>'+escapeHtml(a.path)+'</code><span class="size">'+escapeHtml((a.size/1024).toFixed(1))+'KB</span></li>';
    else html+='<li class="disabled"><code>'+escapeHtml(a.path)+'</code></li>';
  }
  return html+'</ul>';
}
function renderLogs(logs){
  var html='<h4>&sect; 로그</h4>';
  if(!logs||!logs.length)return html+'<p>-</p>';
  var sections='';
  for(var i=0;i<logs.length;i++){
    var log=logs[i];
    if(!log.exists){
      sections+='<div class="log-empty">'+escapeHtml(log.name)+' — 보고서 없음</div>';
    }else{
      var truncMsg=log.truncated?'<span class="log-trunc">마지막 200줄 / 전체 '+escapeHtml(String(log.lines_total))+'줄</span>':'';
      sections+='<details class="log-entry" open><summary>'+escapeHtml(log.name)+truncMsg+'</summary>'
        +'<pre class="log-tail">'+escapeHtml(log.tail)+'</pre></details>';
    }
  }
  return html+'<section class="panel-logs">'+sections+'</section>';
}
function openTaskPanel(taskId){
  var sp='all';try{var m=location.search.match(/[?&]subproject=([^&]+)/);if(m)sp=m[1];}catch(e){}
  fetch('/api/task-detail?task='+encodeURIComponent(taskId)+'&subproject='+encodeURIComponent(sp))
    .then(function(r){return r.json();}).then(function(data){
      var t=document.getElementById('task-panel-title');if(t)t.textContent=data.title||taskId;
      var b=document.getElementById('task-panel-body');
      if(b)b.innerHTML=renderTaskProgressHeader(data.state||null)+renderWbsSection(data.wbs_section_md||'',data.source||'')+renderStateJson(data.state||{})+renderArtifacts(data.artifacts||[])+renderLogs(data.logs||[]);
      var p=document.getElementById('task-panel'),o=document.getElementById('task-panel-overlay');
      if(p){p.classList.add('open');p.dataset.panelMode='task';}if(o)o.removeAttribute('hidden');
    }).catch(function(e){console.error('task-panel error',e);});
}
function closeTaskPanel(){
  var p=document.getElementById('task-panel'),o=document.getElementById('task-panel-overlay');
  if(p)p.classList.remove('open');if(o)o.setAttribute('hidden','');
}
function renderMergePreview(ms){
  var html='';
  if(ms.stale){html+='<div class="merge-stale-banner">⚠ 스캔 결과가 30분 이상 경과 — 재스캔 필요</div>';}
  var state=ms.state||'unknown';
  if(state==='ready'){
    html+='<div class="merge-ready-banner">✅ 모든 Task 완료 · 충돌 없음</div>';
  }else if(state==='waiting'){
    html+='<h4>§ 대기 중인 Task</h4><ul>';
    var pts=ms.pending_tasks||[];
    for(var i=0;i<pts.length;i++){html+='<li>'+escapeHtml(pts[i].id||'')+' ('+escapeHtml(pts[i].phase||'')+')</li>';}
    html+='</ul>';
  }else if(state==='conflict'){
    html+='<h4>§ 충돌 파일</h4><ul class="merge-conflict-file">';
    var conflicts=ms.conflicts||[];
    var autoFiles=ms.auto_merge_files||[];
    var hunkCount=0;
    for(var i=0;i<conflicts.length;i++){
      var c=conflicts[i];var fname=c.file||c.path||'';
      var isAuto=autoFiles.indexOf(fname)>=0;
      if(isAuto){
        html+='<li class="disabled"><code>'+escapeHtml(fname)+'</code> <span>auto-merge 드라이버 적용 예정</span></li>';
      }else{
        html+='<li><code>'+escapeHtml(fname)+'</code>';
        if(c.hunks&&hunkCount<5){
          var hunks=c.hunks.slice(0,5-hunkCount);
          for(var j=0;j<hunks.length;j++){
            html+='<pre class="merge-hunk-preview">'+escapeHtml(hunks[j])+'</pre>';
            hunkCount++;
          }
        }
        html+='</li>';
      }
    }
    html+='</ul>';
  }else{
    html+='<p>스캔 데이터 없음 — <code>scripts/merge-preview-scanner.py</code> 를 실행하세요.</p>';
  }
  return html;
}
function openMergePanel(wpId){
  var sp='all';try{var m=location.search.match(/[?&]subproject=([^&]+)/);if(m)sp=m[1];}catch(e){}
  var panel=document.getElementById('task-panel');
  var title=document.getElementById('task-panel-title');
  var body=document.getElementById('task-panel-body');
  var overlay=document.getElementById('task-panel-overlay');
  function _showPanel(contentHtml){
    if(body)body.innerHTML=contentHtml;
    if(panel){panel.dataset.panelMode='merge';panel.classList.add('open');}
    if(overlay)overlay.removeAttribute('hidden');
  }
  fetch('/api/merge-status?wp='+encodeURIComponent(wpId)+'&subproject='+encodeURIComponent(sp))
    .then(function(r){return r.json();})
    .then(function(ms){
      if(title)title.textContent=wpId+' — 머지 프리뷰';
      _showPanel(renderMergePreview(ms));
    })
    .catch(function(err){
      _showPanel('<p>머지 상태 로드 실패: '+escapeHtml(String(err))+'</p>');
    });
}
document.addEventListener('click',function(e){
  var badge=e.target.closest?e.target.closest('.merge-badge'):null;
  if(!badge&&e.target.classList&&e.target.classList.contains('merge-badge'))badge=e.target;
  if(badge){openMergePanel(badge.getAttribute('data-wp')||'');return;}
  var btn=e.target.closest?e.target.closest('.expand-btn'):null;
  if(!btn&&e.target.classList&&e.target.classList.contains('expand-btn'))btn=e.target;
  if(btn){openTaskPanel(btn.getAttribute('data-task-id')||'');return;}
  if(e.target.id==='task-panel-close'){closeTaskPanel();return;}
  if(e.target.id==='task-panel-overlay'){closeTaskPanel();return;}
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){var p=document.getElementById('task-panel');if(p&&p.classList.contains('open'))closeTaskPanel();}
});
(function initSlidePanelResize(){
  var panel=document.getElementById('task-panel');
  if(!panel)return;
  var handle=panel.querySelector('.slide-panel-resize-handle');
  if(!handle)return;
  try{var saved=localStorage.getItem('task-panel-width');if(saved)panel.style.setProperty('--panel-w',saved);}catch(e){}
  var dragging=false,startX=0,startW=0;
  handle.addEventListener('pointerdown',function(e){
    dragging=true;startX=e.clientX;startW=panel.getBoundingClientRect().width;
    handle.classList.add('dragging');panel.classList.add('resizing');
    try{handle.setPointerCapture(e.pointerId);}catch(_){}
    e.preventDefault();
  });
  handle.addEventListener('pointermove',function(e){
    if(!dragging)return;
    var delta=startX-e.clientX;
    var newW=Math.max(320,Math.min(window.innerWidth*0.98,startW+delta));
    panel.style.setProperty('--panel-w',newW+'px');
  });
  function endDrag(e){
    if(!dragging)return;
    dragging=false;handle.classList.remove('dragging');panel.classList.remove('resizing');
    try{handle.releasePointerCapture(e.pointerId);}catch(_){}
    try{var w=panel.style.getPropertyValue('--panel-w');if(w)localStorage.setItem('task-panel-width',w.trim());}catch(_){}
  }
  handle.addEventListener('pointerup',endDrag);
  handle.addEventListener('pointercancel',endDrag);
  handle.addEventListener('dblclick',function(){
    panel.style.removeProperty('--panel-w');
    try{localStorage.removeItem('task-panel-width');}catch(_){}
  });
})();
"""


def _task_panel_js() -> str:
    """JS for task slide panel. Document-level delegation survives auto-refresh."""
    return _TASK_PANEL_JS


def _task_panel_dom() -> str:
    """Body-level DOM for task slide panel. Body-direct child for auto-refresh isolation."""
    return (
        '<div id="task-panel-overlay" hidden></div>\n'
        '<aside id="task-panel" class="slide-panel" hidden aria-labelledby="task-panel-title">\n'
        '  <div class="slide-panel-resize-handle" aria-hidden="true" title="드래그하여 크기 조절"></div>\n'
        '  <header>\n'
        '    <h3 id="task-panel-title"></h3>\n'
        '    <button id="task-panel-close" aria-label="Close task panel">&#x2715;</button>\n'
        '  </header>\n'
        '  <div id="task-panel-body"></div>\n'
        '</aside>'
    )


def _is_dataclass_instance(value: Any) -> bool:
    """True iff *value* is a dataclass **instance** (not the class object)."""
    return is_dataclass(value) and not isinstance(value, type)


def _asdict_or_none(value):
    """Coerce dataclass / list[dataclass] / None / scalar for JSON-ready output.

    - ``None`` → ``None`` (keeps the ``tmux_panes == null`` acceptance case)
    - ``list`` → new list where every dataclass element is expanded with
      :func:`dataclasses.asdict`, non-dataclass elements pass through.
    - single dataclass → ``asdict(value)``
    - anything else (str/int/dict/...) → returned unchanged
    """
    if value is None:
        return None
    if isinstance(value, list):
        return [asdict(x) if _is_dataclass_instance(x) else x for x in value]
    if _is_dataclass_instance(value):
        return asdict(value)
    return value


# _now_iso_z: moved to monitor_server.api (C0-4).


def _classify_signal_scopes(
    signals: Iterable[SignalEntry],
) -> Tuple[List[SignalEntry], List[SignalEntry]]:
    """Split signal entries into ``(shared_signals, agent_pool_signals)``.

    - ``scope == "shared"`` → shared
    - ``scope.startswith("agent-pool:")`` → agent pool
    - anything else (unknown future scope) → shared (conservative fallback so
      no entry is silently dropped — TSK-01-06 design §3).
    """
    shared: List[SignalEntry] = []
    agent_pool: List[SignalEntry] = []
    for sig in signals:
        scope = getattr(sig, "scope", None) or ""
        if scope.startswith(_AGENT_POOL_SCOPE_PREFIX):
            agent_pool.append(sig)
        else:
            shared.append(sig)
    return shared, agent_pool


# ---------------------------------------------------------------------------
# Project-level pane/signal filter helpers (TSK-00-02)
# ---------------------------------------------------------------------------


def _filter_panes_by_project(
    panes: Optional[List["PaneInfo"]],
    project_root: str,
    project_name: str,
) -> Optional[List["PaneInfo"]]:
    """Return panes that belong to the given project.

    A pane passes the filter if **either** condition is true:

    1. ``pane_current_path`` equals *project_root* or is a subdirectory of it
       (``pane_current_path.startswith(root + os.sep)``).
    2. ``window_name`` matches the ``WP-*-{project_name}`` pattern, i.e. it starts
       with ``"WP-"`` and ends with ``"-{project_name}"``.

    Special cases:

    - If *panes* is ``None`` (tmux not installed signal), ``None`` is returned
      unchanged so the caller can distinguish "no tmux" from "tmux with 0 panes".
    - Trailing ``os.sep`` on *project_root* is normalised before comparison.
    - The original list is never mutated — a new list is returned.

    Args:
        panes: Output of ``list_tmux_panes()`` — ``None`` or ``List[PaneInfo]``.
        project_root: Absolute path to the project root directory.
        project_name: Short project name used in WP window-name pattern.

    Returns:
        ``None`` if *panes* is ``None``, otherwise a filtered ``List[PaneInfo]``.
    """
    if panes is None:
        return None

    root = project_root.rstrip(os.sep)
    root_sep = root + os.sep  # pre-computed once; reused per pane
    suffix = f"-{project_name}"
    result: List[PaneInfo] = []
    for pane in panes:
        cwd = getattr(pane, "pane_current_path", "") or ""
        wname = getattr(pane, "window_name", "") or ""
        # Condition 1: cwd is the root dir or a strict subdirectory.
        if cwd == root or cwd.startswith(root_sep):
            result.append(pane)
            continue
        # Condition 2: window_name matches WP-*-{project_name}.
        if wname.startswith("WP-") and wname.endswith(suffix):
            result.append(pane)
    return result


def _filter_signals_by_project(
    signals: List[SignalEntry],
    project_name: str,
) -> List[SignalEntry]:
    """Return signals whose scope belongs to the given project.

    A signal passes the filter if its ``scope`` field satisfies:

    - ``scope == project_name``  (exact match), **or**
    - ``scope.startswith(project_name + "-")``  (sub-project prefix match).

    This deliberately excludes:

    - ``"shared"`` scope (cross-project shared signals).
    - ``"agent-pool:*"`` scope (session-local pool signals).
    - Other-project scopes including false-positive prefixes like ``myproj2``
      when *project_name* is ``myproj`` (the ``"-"`` separator prevents it).

    Args:
        signals: List of ``SignalEntry`` objects from ``scan_signals()``.
        project_name: Short project name to match against.

    Returns:
        A new list containing only matching signal entries.
    """
    prefix = project_name + "-"
    result: List[SignalEntry] = []
    for sig in signals:
        scope = getattr(sig, "scope", "") or ""
        if (
            scope == project_name
            or scope.startswith(prefix)
            or scope.startswith(_AGENT_POOL_SCOPE_PREFIX)
        ):
            result.append(sig)
    return result


# ---------------------------------------------------------------------------
# /api/state 쿼리 파라미터 헬퍼 (순수 함수 — 테스트 용이)
# ---------------------------------------------------------------------------


def _parse_state_query_params(query_string: str) -> dict:
    """Parse /api/state query parameters into a dict with typed defaults.

    Parameters
    ----------
    query_string:
        Raw query string (without leading ``?``). Empty string is accepted.

    Returns
    -------
    dict with keys:
        ``subproject`` (str, default ``"all"``)
        ``lang``       (str, default ``"ko"``)
        ``include_pool`` (bool, default ``False``)
        ``refresh``    (str | None, default ``None``)
    """
    from urllib.parse import parse_qs

    parsed = parse_qs(query_string, keep_blank_values=False)

    subproject = parsed.get("subproject", ["all"])[0] or "all"
    lang = parsed.get("lang", ["ko"])[0] or "ko"
    raw_pool = parsed.get("include_pool", ["0"])[0]
    include_pool = raw_pool.strip() == "1"
    refresh_vals = parsed.get("refresh")
    refresh = refresh_vals[0] if refresh_vals else None

    return {
        "subproject": subproject,
        "lang": lang,
        "include_pool": include_pool,
        "refresh": refresh,
    }


def _resolve_effective_docs_dir(docs_dir: str, subproject: str) -> str:
    """Resolve the effective docs directory for the given subproject.

    ``subproject == "all"`` or empty/None → *docs_dir* unchanged.
    Otherwise returns ``os.path.join(docs_dir, subproject)``.

    Path existence is *not* checked here — callers (scan_tasks/scan_features)
    return empty lists for non-existent directories.
    """
    if not subproject or subproject == "all":
        return docs_dir
    return os.path.join(docs_dir, subproject)


def _get_field(item, field: str, default: str = "") -> str:
    """Return *field* from *item* regardless of whether it is a dict or dataclass.

    Centralises the ``isinstance(item, dict)`` branching used in several filter
    helpers so each call site only needs one expression instead of a ternary.
    """
    if isinstance(item, dict):
        return item.get(field, default) or default
    return getattr(item, field, default) or default


def _apply_subproject_filter(raw: dict, subproject: str) -> dict:
    """Apply subproject filter to shared_signals and tmux_panes in *raw*.

    When ``subproject == "all"`` the dict is returned unchanged.

    For a specific subproject, ``shared_signals`` entries whose ``task_id``
    starts with a WP prefix (e.g. ``"WP-00-"`` signals) are kept only if
    they do *not* start with ``"WP-00-"`` — or rather: we keep signals that
    are either:
    - not WP-scoped (task_id does not match ``WP-NN-`` pattern), or
    - WP-scoped to the requested subproject.

    ``tmux_panes`` entries are filtered by ``window_name`` containing the
    subproject slug.

    This is a pure function — *raw* is not mutated in-place; a new dict is
    returned with the filtered lists.
    """
    if subproject == "all":
        return raw

    result = dict(raw)
    sp_lower = subproject.lower()

    # Filter shared_signals: keep non-WP signals, and WP-scoped signals only
    # when the task_id contains the requested subproject slug.
    # (Best-effort heuristic; full naming convention wired in TSK-00-03.)
    raw_signals = raw.get("shared_signals") or []

    def _sig_matches(sig) -> bool:
        task_id = _get_field(sig, "task_id")
        if _WP_SIGNAL_PREFIX_RE.match(task_id):
            return sp_lower in task_id.lower()
        return True  # non-WP signals are kept

    result["shared_signals"] = [s for s in raw_signals if _sig_matches(s)]

    # Filter tmux_panes: keep panes whose window_name contains subproject slug.
    raw_panes = raw.get("tmux_panes") or []

    def _pane_matches(p) -> bool:
        return sp_lower in _get_field(p, "window_name").lower()

    result["tmux_panes"] = [p for p in raw_panes if _pane_matches(p)]

    return result


def _apply_include_pool(raw: dict, include_pool: bool) -> dict:
    """Zero out agent_pool_signals when *include_pool* is False.

    Returns a new dict (does not mutate *raw*).
    """
    if include_pool:
        return raw
    result = dict(raw)
    result["agent_pool_signals"] = []
    return result


def _build_render_state(
    project_root: str,
    docs_dir: str,
    scan_tasks: Callable[[Any], List[WorkItem]],
    scan_features: Callable[[Any], List[WorkItem]],
    scan_signals: Callable[[], List[SignalEntry]],
    list_tmux_panes: Callable[[], Optional[List[PaneInfo]]],
    subproject: str = "all",
    lang: str = "ko",
) -> dict:
    """Collect state with raw dataclass instances intact (for HTML rendering).

    The HTML renderer (``render_dashboard`` and ``_section_*`` / ``_render_*``
    helpers) accesses fields via ``getattr(item, "id")``, so list items must
    remain dataclass instances — routing through :func:`_asdict_or_none` would
    convert them to ``dict`` and break every ``getattr`` call (regression
    found by TSK-03-02 QA retest: task-row id/title/status spans rendered as
    empty strings because ``getattr(dict, "id")`` returns ``None``).

    Returns a dict with the 8 original keys plus 4 new keys added by
    TSK-01-02: ``project_name``, ``subproject``, ``available_subprojects``,
    ``is_multi_mode``. The 5 list-valued keys remain as dataclass instances.

    Args:
        project_root: absolute project root path.
        docs_dir: effective docs directory (may be a subproject subdir).
        scan_tasks: callable that accepts docs_dir and returns WorkItem list.
        scan_features: callable that accepts docs_dir and returns WorkItem list.
        scan_signals: callable that returns SignalEntry list.
        list_tmux_panes: callable that returns PaneInfo list or None.
        subproject: active subproject slug (default ``"all"``).
        lang: active language (default ``"ko"``).
    """
    tasks = list(scan_tasks(docs_dir) or [])
    features = list(scan_features(docs_dir) or [])
    shared_signals, agent_pool_signals = _classify_signal_scopes(
        scan_signals() or []
    )
    panes = list_tmux_panes()

    # discover subprojects from original docs_dir root
    # (docs_dir may already be narrowed to subproject; use project_root to
    # find the original docs root — but for discover we need the top-level
    # docs dir, which is stored in the server's docs_dir attribute).
    available_subprojects = discover_subprojects(docs_dir)
    is_multi_mode = bool(available_subprojects)
    project_name = os.path.basename(os.path.normpath(project_root)) if project_root else ""

    wp_titles = _load_wbs_wp_titles(Path(docs_dir)) if docs_dir else {}

    return {
        "generated_at": _now_iso_z(),
        "project_root": project_root or "",
        "docs_dir": docs_dir or "",
        "wbs_tasks": tasks,
        "features": features,
        "shared_signals": shared_signals,
        "agent_pool_signals": agent_pool_signals,
        "tmux_panes": panes,
        # new fields
        "project_name": project_name,
        "subproject": subproject,
        "available_subprojects": available_subprojects,
        "is_multi_mode": is_multi_mode,
        "lang": lang,
        "wp_titles": wp_titles,
    }


def _build_state_snapshot(
    project_root: str,
    docs_dir: str,
    scan_tasks: Callable[[Any], List[WorkItem]],
    scan_features: Callable[[Any], List[WorkItem]],
    scan_signals: Callable[[], List[SignalEntry]],
    list_tmux_panes: Callable[[], Optional[List[PaneInfo]]],
) -> dict:
    """Build the dict that becomes the /api/state response body.

    The scanner callables are injected so unit tests can supply stubs. Production
    code passes the module-level ``scan_tasks``/``scan_features``/``scan_signals``/
    ``list_tmux_panes`` functions directly.

    Signal scope classification is delegated to :func:`_classify_signal_scopes`
    (see that helper for the conservative "unknown → shared" fallback).

    ``tmux_panes`` is preserved as ``None`` when the scanner signals "tmux not
    installed" so clients can distinguish it from the empty-list "no panes
    running" case (TSK-01-06 acceptance 2).
    """
    raw = _build_render_state(
        project_root,
        docs_dir,
        scan_tasks,
        scan_features,
        scan_signals,
        list_tmux_panes,
    )
    return {
        "generated_at": raw["generated_at"],
        "project_root": raw["project_root"],
        "docs_dir": raw["docs_dir"],
        "wbs_tasks": _asdict_or_none(raw["wbs_tasks"]),
        "features": _asdict_or_none(raw["features"]),
        "shared_signals": _asdict_or_none(raw["shared_signals"]),
        "agent_pool_signals": _asdict_or_none(raw["agent_pool_signals"]),
        "tmux_panes": _asdict_or_none(raw["tmux_panes"]),
        "merge_summary": _collect_merge_summary(docs_dir),
    }


def _json_response(handler, status: int, payload) -> None:
    """Write *payload* as JSON to *handler* with the mandated headers.

    Body encoding: ``json.dumps(payload, default=str, ensure_ascii=False)`` then
    UTF-8. ``default=str`` covers ``datetime``/``Path``/``Decimal`` drift — the
    production pipeline already stores ISO strings, this is a defensive net.
    ``ensure_ascii=False`` keeps Korean/non-ASCII titles legible.

    Headers always set:

    - ``Content-Type: application/json; charset=utf-8``
    - ``Content-Length: <len(body_bytes)>``
    - ``Cache-Control: no-store``

    Feature monitor-perf — ETag/304:
    - 응답 본문에 대해 weak ETag를 계산하여 ``ETag`` 헤더로 노출한다.
    - 요청의 ``If-None-Match`` 헤더가 ETag와 일치하면 본문 없이 304를 반환.
    - etag_cache 모듈이 없는 레거시 환경에서는 기존 동작 그대로.
    """
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")

    # ETag/304 처리 (monitor-perf) — lazy-load etag_cache on first call
    _ensure_etag_cache()
    if _compute_etag is not None and _check_if_none_match is not None:
        etag = _compute_etag(body)
        if _check_if_none_match(handler, etag):
            # 304 Not Modified — 본문 전송 없음
            handler.send_response(304)
            handler.send_header("ETag", etag)
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            return
        # 200 — ETag 헤더 추가 후 본문 전송 (헤더 순서: ETag → Content-Type → Content-Length → Cache-Control)
        handler.send_response(status)
        handler.send_header("ETag", etag)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)
        return

    # Fallback: etag_cache 없음 — 기존 동작
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _json_error(handler, status: int, message: str) -> None:
    """Send a standard JSON error envelope: ``{"error": <msg>, "code": <status>}``."""
    _json_response(handler, status, {"error": message, "code": status})


def _server_attr(handler, name: str, default: str = "") -> str:
    """Read ``handler.server.<name>`` defensively, returning a string.

    Missing ``server`` attribute or missing/blank attribute value degrade to
    *default*. Any non-string value is coerced via :func:`str`.
    """
    server = getattr(handler, "server", None)
    value = getattr(server, name, default) or default
    return str(value)


# _handle_api_state: moved to handlers_state.py [core-http-split:refactor-01]
# facade re-export via try/except block at bottom of this file.


# ---------------------------------------------------------------------------
# [core-http-split:C2-1] HTTP Handler — facade re-export from handlers.py
# ---------------------------------------------------------------------------
# MonitorHandler가 handlers.py로 이관되었다. core.py는 facade 재-export만 수행.
# handlers_pane / handlers_graph / handlers_state 도 동일하게 facade 처리.
# flat-load 컨텍스트(test spec_from_file_location)에서 monitor_server.handlers를
# dotted import할 수 없는 경우를 대비해 try/except 로드 패턴을 동일하게 적용한다.

import importlib.util as _c21_ilu
_c21_pkg_dir = Path(__file__).resolve().parent


def _c21_load_mod(logical_name: str, fname: str):
    """handler 서브모듈을 안정적인 이름으로 로드한다.

    flat-load 컨텍스트(test_monitor_module_split.py 등)에서
    test 픽스처가 sys.modules에서 "monitor_server.*" 키를 제거하더라도
    "monitor_server_*_impl" 형태의 키는 제거되지 않아 모듈 객체가
    동일한 id로 유지된다. 따라서 do_GET.__globals__ 는 항상 같은 dict를
    참조하고, mock.patch.object(sys.modules[key], ...) 패치가 유효하다.

    동작:
    1. "monitor_server_{logical_name}_impl" 키 확인 (flat-load 안정 키)
    2. "monitor_server.{logical_name}" 키 확인 (패키지 컨텍스트)
    3. 없으면 file-load 후 양쪽 키 모두 등록
    """
    stable_key = f"monitor_server_{logical_name}_impl"
    pkg_key = f"monitor_server.{logical_name}"

    # 1. 이미 안정 키로 로드된 경우
    existing = sys.modules.get(stable_key)
    if existing is not None:
        # 패키지 키도 동기화
        if sys.modules.get(pkg_key) is not existing:
            sys.modules[pkg_key] = existing
        return existing

    # 2. 패키지 키로만 로드된 경우 → 안정 키에도 등록
    existing = sys.modules.get(pkg_key)
    if existing is not None:
        sys.modules[stable_key] = existing
        return existing

    # 3. 파일 로드
    path = _c21_pkg_dir / fname
    if not path.exists():
        return None
    spec = _c21_ilu.spec_from_file_location(stable_key, str(path))
    if spec is None:
        return None
    mod = _c21_ilu.module_from_spec(spec)
    sys.modules[stable_key] = mod
    sys.modules[pkg_key] = mod  # 패키지 키도 동일 객체로 등록
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# 패키지 import 시도 → 실패하면 파일 로드로 폴백
try:
    from monitor_server.handlers import MonitorHandler  # noqa: F401,E402
    from monitor_server.handlers_pane import (  # noqa: F401,E402
        _handle_pane_html,
        _handle_pane_api,
    )
    from monitor_server.handlers_graph import (  # noqa: F401,E402
        _handle_graph_api,
        _handle_api_task_detail,
    )
    from monitor_server.handlers_state import _handle_api_state  # noqa: F401,E402
    # 패키지 import 성공 시에도 안정 키로 alias 등록
    # (test_monitor_module_split가 "monitor_server.*" 키를 지워도 _impl 키는 유지)
    for _c21_name, _c21_file in [
        ("handlers", "handlers.py"),
        ("handlers_pane", "handlers_pane.py"),
        ("handlers_graph", "handlers_graph.py"),
        ("handlers_state", "handlers_state.py"),
    ]:
        _c21_pkg_k = f"monitor_server.{_c21_name}"
        _c21_stable_k = f"monitor_server_{_c21_name}_impl"
        _c21_m = sys.modules.get(_c21_pkg_k)
        if _c21_m is not None and sys.modules.get(_c21_stable_k) is None:
            sys.modules[_c21_stable_k] = _c21_m
except (ImportError, ModuleNotFoundError):
    _c21_handlers = _c21_load_mod("handlers", "handlers.py")
    if _c21_handlers is not None:
        MonitorHandler = _c21_handlers.MonitorHandler  # type: ignore[assignment,misc]

    _c21_pane = _c21_load_mod("handlers_pane", "handlers_pane.py")
    if _c21_pane is not None:
        _handle_pane_html = _c21_pane._handle_pane_html  # type: ignore[assignment]
        _handle_pane_api = _c21_pane._handle_pane_api  # type: ignore[assignment]

    _c21_graph = _c21_load_mod("handlers_graph", "handlers_graph.py")
    if _c21_graph is not None:
        _handle_graph_api = _c21_graph._handle_graph_api  # type: ignore[assignment]
        _handle_api_task_detail = _c21_graph._handle_api_task_detail  # type: ignore[assignment]

    _c21_state = _c21_load_mod("handlers_state", "handlers_state.py")
    if _c21_state is not None:
        _handle_api_state = _c21_state._handle_api_state  # type: ignore[assignment]


class ThreadingMonitorServer(ThreadingHTTPServer):
    """ThreadingHTTPServer subclass that carries server-wide config attributes.

    Attributes injected by ``main()``:
        project_root (str): resolved project root path.
        docs_dir (str): docs directory path.
        max_pane_lines (int): scrollback line cap for pane capture.
        refresh_seconds (int): dashboard meta-refresh interval.
        no_tmux (bool): when True, tmux calls should be skipped.
        plugin_root (str): plugin root directory for static file serving
            (TSK-03-03). Resolved by ``_resolve_plugin_root()`` in ``main()``.

    ``allow_reuse_address = True`` prevents ``OSError: Address already in use``
    when the server restarts quickly (e.g., during test runs).
    """

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, **kwargs):
        super().__init__(server_address, RequestHandlerClass, **kwargs)
        # Attributes will be set by main() after construction.
        self.project_root: str = ""
        self.docs_dir: str = ""
        self.max_pane_lines: int = 500
        self.refresh_seconds: int = 3
        self.no_tmux: bool = False
        self.plugin_root: str = ""


# ---------------------------------------------------------------------------
# CLI entry point (TSK-01-01)
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    """Return the ArgumentParser for monitor-server.py.

    All arguments have defaults as specified in the TSK-01-01 PRD:
        --port             7321
        --docs             "docs"
        --project-root     os.getcwd()
        --max-pane-lines   500
        --refresh-seconds  3
        --no-tmux          False (store_true flag)
    """
    parser = argparse.ArgumentParser(
        prog="monitor-server.py",
        description="dev-plugin monitor HTTP server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7321,
        metavar="PORT",
        help="TCP port to listen on (default: 7321)",
    )
    parser.add_argument(
        "--docs",
        default="docs",
        metavar="DIR",
        help="docs directory path (default: docs)",
    )
    parser.add_argument(
        "--project-root",
        default=os.getcwd(),
        metavar="DIR",
        help="project root directory (default: $PWD)",
    )
    parser.add_argument(
        "--max-pane-lines",
        type=int,
        default=500,
        metavar="N",
        help="maximum scrollback lines for pane capture (default: 500)",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=3,
        metavar="N",
        help="dashboard meta-refresh interval in seconds (default: 3)",
    )
    parser.add_argument(
        "--no-tmux",
        action="store_true",
        default=False,
        help="disable tmux integration (no pane listing/capture)",
    )
    return parser


def pid_file_path(port: int) -> Path:
    return Path(tempfile.gettempdir()) / f"dev-monitor-{port}.pid"


def cleanup_pid_file(pid_path: Path) -> None:
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass


def _setup_signal_handler(server, pid_path: Path) -> None:
    if sys.platform == "win32":
        return

    def _handler(signum, frame):  # noqa: ANN001
        t = threading.Thread(target=server.shutdown, daemon=True)
        t.start()

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError):
        pass


def parse_args(argv=None):
    return build_arg_parser().parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Parse CLI args, create ThreadingMonitorServer, and serve_forever.

    Binds exclusively to ``127.0.0.1`` (0.0.0.0 is prohibited per PRD §4.1).
    Config attributes (docs_dir, project_root, max_pane_lines, refresh_seconds,
    no_tmux) are injected into the server instance so MonitorHandler can read
    them via ``self.server.<attr>``.

    Graceful shutdown on SIGTERM or KeyboardInterrupt.
    """
    args = parse_args(argv)
    
    port = args.port
    pid_path = pid_file_path(port)
    with open(str(pid_path), "w", encoding="utf-8", newline="\n") as _f:
        _f.write(str(os.getpid()))

    server = ThreadingMonitorServer(("127.0.0.1", port), MonitorHandler)
    server.project_root = args.project_root
    server.docs_dir = args.docs
    server.max_pane_lines = args.max_pane_lines
    server.refresh_seconds = args.refresh_seconds
    server.no_tmux = args.no_tmux
    server.plugin_root = _resolve_plugin_root()  # static file serving

    _setup_signal_handler(server, pid_path)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        cleanup_pid_file(pid_path)


# ---------------------------------------------------------------------------
# [core-renderer-split:C1-1+] renderer facade re-exports
# ---------------------------------------------------------------------------
# render_dashboard 와 외부 테스트가 core._section_* / core._render_* 로 접근하므로
# 동일 이름으로 재-export 한다. 본문은 monitor_server/renderers/{module}.py 소관.
# 이 블록은 파일 하단에 위치해야 한다 — renderers/_util.py 가 core 심볼을 late-import
# 하므로 core 모듈 초기화 완료 후에 renderers 패키지를 로드해야 순환 참조가 없다.

_c2b_pkg_dir = Path(__file__).resolve().parent


def _c2b_load_renderer(module_name: str):
    """renderers 서브모듈을 flat-load 환경에서도 안전하게 로드한다.

    패키지 컨텍스트(정상 import)에서는 sys.modules에서 바로 찾는다.
    flat-load 컨텍스트(test spec_from_file_location)에서는 current module을
    monitor_server.core로 등록하고 renderers를 직접 파일 로드한다.
    _util.py가 'from monitor_server import core'를 사용하므로 monitor_server.core
    를 미리 등록해두어야 순환 참조를 피할 수 있다.
    """
    import importlib.util as _ilu

    pkg_key = f"monitor_server.renderers.{module_name}"
    existing = sys.modules.get(pkg_key)
    if existing is not None:
        return existing

    renderers_dir = _c2b_pkg_dir / "renderers"

    # renderers 패키지 __init__ 등록 (아직 없으면)
    pkg_init_key = "monitor_server.renderers"
    if sys.modules.get(pkg_init_key) is None:
        init_path = renderers_dir / "__init__.py"
        if init_path.exists():
            _init_spec = _ilu.spec_from_file_location(pkg_init_key, str(init_path))
            if _init_spec is not None:
                _init_mod = _ilu.module_from_spec(_init_spec)
                sys.modules[pkg_init_key] = _init_mod
                try:
                    _init_spec.loader.exec_module(_init_mod)  # type: ignore[union-attr]
                except Exception:
                    del sys.modules[pkg_init_key]

    # 대상 모듈 로드
    mod_path = renderers_dir / f"{module_name}.py"
    if not mod_path.exists():
        return None
    _spec = _ilu.spec_from_file_location(pkg_key, str(mod_path))
    if _spec is None:
        return None
    mod = _ilu.module_from_spec(_spec)
    sys.modules[pkg_key] = mod
    try:
        _spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        sys.modules.pop(pkg_key, None)
        return None
    return mod


try:
    from .renderers.wp import _section_wp_cards, _wp_busy_indicator_html  # noqa: F401,E402
except (ImportError, AttributeError):
    try:
        _c2b_wp = _c2b_load_renderer("wp")
        if _c2b_wp is not None:
            _section_wp_cards = _c2b_wp._section_wp_cards  # type: ignore[assignment]
            _wp_busy_indicator_html = _c2b_wp._wp_busy_indicator_html  # type: ignore[assignment]
    except (ImportError, AttributeError):
        pass  # flat-load 컨텍스트에서 renderers 로드 불가 — 해당 심볼 미노출(정상)
try:
    from .renderers.team import _section_team, _render_pane_row  # noqa: F401,E402
except (ImportError, AttributeError):
    try:
        _c2b_team = _c2b_load_renderer("team")
        if _c2b_team is not None:
            _section_team = _c2b_team._section_team  # type: ignore[assignment]
            _render_pane_row = _c2b_team._render_pane_row  # type: ignore[assignment]
    except (ImportError, AttributeError):
        pass  # flat-load 컨텍스트에서 renderers 로드 불가 — thin wrapper 사용
try:
    from .renderers.subagents import _section_subagents, _render_subagent_row, _SUBAGENT_INFO  # noqa: F401,E402
except (ImportError, AttributeError):
    try:
        _c2b_sub = _c2b_load_renderer("subagents")
        if _c2b_sub is not None:
            _section_subagents = _c2b_sub._section_subagents  # type: ignore[assignment]
            _render_subagent_row = _c2b_sub._render_subagent_row  # type: ignore[assignment]
            _SUBAGENT_INFO = _c2b_sub._SUBAGENT_INFO  # type: ignore[assignment]
    except (ImportError, AttributeError):
        pass  # flat-load 컨텍스트 — thin wrapper 사용
try:
    from .renderers.activity import (  # noqa: F401,E402
        _section_live_activity, _render_arow, _live_activity_rows,
        _live_activity_details_wrap, _fmt_hms, _fmt_elapsed_short,
        _event_to_sig_kind, _arow_data_to,
    )
except (ImportError, AttributeError):
    try:
        _c2b_act = _c2b_load_renderer("activity")
        if _c2b_act is not None:
            _section_live_activity = _c2b_act._section_live_activity  # type: ignore[assignment]
            _render_arow = _c2b_act._render_arow  # type: ignore[assignment]
            _live_activity_rows = _c2b_act._live_activity_rows  # type: ignore[assignment]
            _live_activity_details_wrap = _c2b_act._live_activity_details_wrap  # type: ignore[assignment]
            _fmt_hms = _c2b_act._fmt_hms  # type: ignore[assignment]
            _fmt_elapsed_short = _c2b_act._fmt_elapsed_short  # type: ignore[assignment]
            _event_to_sig_kind = _c2b_act._event_to_sig_kind  # type: ignore[assignment]
            _arow_data_to = _c2b_act._arow_data_to  # type: ignore[assignment]
    except (ImportError, AttributeError):
        pass  # flat-load 컨텍스트 — thin wrapper 사용
# === /renderer facade ===


if __name__ == "__main__":
    main()
