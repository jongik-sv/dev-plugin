#!/usr/bin/env python3
"""dev-monitor HTTP 서버 (단일 파일).

본 파일은 여러 Task에 걸쳐 점진적으로 채워진다. TSK-01-03 시점의 적재물:

- 시그널 스캐너: ``scan_signals()``
- tmux pane 스캐너: ``list_tmux_panes()``, ``capture_pane(pane_id)``
- 데이터 클래스: ``SignalEntry``, ``PaneInfo`` (TRD §5.2 / §5.3)

후속 Task(TSK-01-01/02/04/05/06)가 HTTP 서버 뼈대와 라우팅, WBS/Feature 스캐너,
HTML 대시보드 렌더러, JSON 스냅샷 엔드포인트를 같은 파일에 추가한다. 본 Task는
HTTP 레이어와 독립적인 순수 함수만 배치하므로 병렬·후행 Task와 충돌하지 않는다.

구현 원칙:
- Python 3.8+ stdlib 전용 (``CLAUDE.md`` 규약)
- 모든 ``subprocess.run`` 은 ``shell=False`` 리스트 인자 + 명시 ``timeout``
- 모든 실패 경로(디렉터리 부재, tmux 부재, 서버 미기동, 잘못된 pane_id,
  subprocess 오류/타임아웃)는 정의된 반환 값으로 흡수 — 예외는
  ``capture_pane`` 의 pane_id 형식 위반(ValueError)만 허용
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit


# ---------------------------------------------------------------------------
# Constants (TSK-01-03)
# ---------------------------------------------------------------------------

_SIGNAL_KINDS = {"running", "done", "failed", "bypassed"}

_TMUX_FMT = (
    "#{window_name}\t#{window_id}\t#{pane_id}\t#{pane_index}\t"
    "#{pane_current_path}\t#{pane_current_command}\t#{pane_pid}\t#{pane_active}"
)

_PANE_ID_RE = re.compile(r"^%\d+$")

# CSI-style ANSI escape sequences (color, cursor, etc.).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# tmux scrollback depth passed to ``capture-pane -S``. Negative = lines from bottom.
_CAPTURE_PANE_SCROLLBACK = "-500"

# subprocess timeouts (seconds). Kept as named constants so test assertions and
# the implementation reference a single source of truth.
_LIST_PANES_TIMEOUT = 2
_CAPTURE_PANE_TIMEOUT = 3


# ---------------------------------------------------------------------------
# Dataclasses (TRD §5.2, §5.3)
# ---------------------------------------------------------------------------


@dataclass
class SignalEntry:
    """Signal file 메타데이터 (TRD §5.2).

    Attributes:
        name: 파일명 (예: ``TSK-01-02.done``).
        kind: 확장자로 결정되는 종류 (``running``/``done``/``failed``/``bypassed``).
        task_id: 파일명 stem (확장자 제외).
        mtime: ISO-8601 UTC 수정 시각 문자열.
        scope: ``shared`` 또는 ``agent-pool:{timestamp}``.
    """

    name: str
    kind: str
    task_id: str
    mtime: str
    scope: str


@dataclass
class PaneInfo:
    """tmux pane 메타데이터 (TRD §5.3).

    필드명은 ``tmux list-panes -F`` 포맷 토큰과 1:1 매핑된다.
    """

    window_name: str
    window_id: str
    pane_id: str
    pane_index: int
    pane_current_path: str
    pane_current_command: str
    pane_pid: int
    is_active: bool


# ---------------------------------------------------------------------------
# scan_signals
# ---------------------------------------------------------------------------


def _iso_mtime(path: str) -> str:
    """Return ISO-8601 UTC mtime string for *path*.

    Fallback to empty string if stat fails — caller stays exception-free.
    """
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _signal_entry(path: str, scope: str) -> Optional[SignalEntry]:
    """Build a SignalEntry from *path* or return None if extension is unknown."""
    name = os.path.basename(path)
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        return None
    if ext not in _SIGNAL_KINDS:
        return None
    return SignalEntry(
        name=name,
        kind=ext,
        task_id=stem,
        mtime=_iso_mtime(path),
        scope=scope,
    )


def _walk_signal_entries(root: str, scope: str) -> List[SignalEntry]:
    """Recursively collect valid ``SignalEntry`` items under *root* with *scope*.

    Returns ``[]`` if *root* is not an existing directory — callers do not need to
    pre-check ``os.path.isdir``. Files with unknown extensions are silently
    skipped by ``_signal_entry``.
    """
    if not os.path.isdir(root):
        return []
    collected: List[SignalEntry] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            entry = _signal_entry(full, scope)
            if entry is not None:
                collected.append(entry)
    return collected


def scan_signals() -> List[SignalEntry]:
    """Enumerate signal files under ``${TMPDIR}``.

    Scope resolution:

    - ``${TMPDIR}/claude-signals/**`` (recursive) → ``scope="shared"``
    - ``${TMPDIR}/agent-pool-signals-*/**`` (recursive) →
      ``scope="agent-pool:{timestamp}"`` where ``{timestamp}`` is the directory-name
      suffix after the ``agent-pool-signals-`` prefix (preserves the trailing
      ``-$$`` PID used by agent-pool).

    Files whose extension is not one of ``running``/``done``/``failed``/``bypassed``
    are silently skipped. Missing directories are not errors — they simply yield
    zero entries.
    """
    tmp_root = tempfile.gettempdir()
    entries: List[SignalEntry] = []

    # (A) Shared scope — recursive walk under claude-signals/
    entries.extend(_walk_signal_entries(os.path.join(tmp_root, "claude-signals"), "shared"))

    # (B) Agent-pool scope — each agent-pool-signals-{timestamp}/ directory
    prefix = "agent-pool-signals-"
    for pool_dir in glob.glob(os.path.join(tmp_root, f"{prefix}*")):
        pool_name = os.path.basename(pool_dir)
        timestamp = pool_name[len(prefix):] if pool_name.startswith(prefix) else pool_name
        entries.extend(_walk_signal_entries(pool_dir, f"agent-pool:{timestamp}"))

    return entries


# ---------------------------------------------------------------------------
# list_tmux_panes
# ---------------------------------------------------------------------------


def list_tmux_panes() -> Optional[List[PaneInfo]]:
    """Return the list of tmux panes, or ``None`` if tmux is not installed.

    Return value contract (per TSK acceptance):

    - tmux binary unreachable (``shutil.which("tmux") is None``) → ``None``
    - tmux present but no server running (stderr contains ``"no server running"``
      or returncode != 0) → ``[]``
    - tmux present and server alive → ``list[PaneInfo]``
    - subprocess.TimeoutExpired / OSError → ``[]`` (never propagate)

    Exceptions are suppressed so callers can branch on ``is None`` /
    ``len(...) == 0`` without try/except.
    """
    if shutil.which("tmux") is None:
        return None

    cmd = ["tmux", "list-panes", "-a", "-F", _TMUX_FMT]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_LIST_PANES_TIMEOUT,
            check=False,
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return []

    if completed.returncode != 0:
        # "no server running" is the common benign failure; other non-zero
        # exit codes also degrade gracefully.
        return []

    panes: List[PaneInfo] = []
    for raw_line in (completed.stdout or "").splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            continue
        cols = line.split("\t")
        if len(cols) != 8:
            # Defensive: pane_current_path may contain tabs if shell PS1 misbehaves.
            continue
        (window_name, window_id, pane_id, pane_index,
         pane_current_path, pane_current_command, pane_pid, pane_active) = cols
        try:
            pane_index_i = int(pane_index)
            pane_pid_i = int(pane_pid)
        except ValueError:
            continue
        panes.append(
            PaneInfo(
                window_name=window_name,
                window_id=window_id,
                pane_id=pane_id,
                pane_index=pane_index_i,
                pane_current_path=pane_current_path,
                pane_current_command=pane_current_command,
                pane_pid=pane_pid_i,
                is_active=(pane_active == "1"),
            )
        )
    return panes


# ---------------------------------------------------------------------------
# capture_pane
# ---------------------------------------------------------------------------


def capture_pane(pane_id: str) -> str:
    """Return tmux pane scrollback as plain text (ANSI escapes stripped).

    Contract:

    - ``pane_id`` must match ``^%\\d+$`` — otherwise ``ValueError`` is raised so
      the HTTP layer can map to HTTP 400 (per TSK spec "400 예정").
    - Non-existent panes or other tmux failures do **not** raise — the stderr
      string is returned verbatim so the UI can display it.
    - ``subprocess.TimeoutExpired`` is converted to a human-readable string.
    - Successful captures pass through ``_ANSI_RE`` to drop color/cursor codes.
    """
    if not isinstance(pane_id, str) or not _PANE_ID_RE.fullmatch(pane_id):
        raise ValueError(f"invalid pane_id: {pane_id!r} (must match ^%\\d+$)")

    cmd = ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", _CAPTURE_PANE_SCROLLBACK]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_CAPTURE_PANE_TIMEOUT,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"tmux capture-pane timed out after {_CAPTURE_PANE_TIMEOUT}s for {pane_id}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"tmux capture-pane failed for {pane_id}: {exc}"

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        detail = stderr if stderr else f"exited with code {completed.returncode}"
        return f"{detail} (pane {pane_id})"

    return _ANSI_RE.sub("", completed.stdout or "")


# ---------------------------------------------------------------------------
# --- scan functions (TSK-01-02) ---
# ---------------------------------------------------------------------------

_MAX_STATE_BYTES = 1 * 1024 * 1024  # 1 MiB
_PHASE_TAIL_LIMIT = 10
_ERROR_CAP = 500


@dataclass(frozen=True)
class PhaseEntry:
    """state.json.phase_history 원소를 얇게 감싼 dataclass.

    ``from``/``to`` 는 Python 예약어이므로 ``from_status``/``to_status`` 로 매핑한다.
    """

    event: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    at: Optional[str]
    elapsed_seconds: Optional[float] = None


@dataclass
class WorkItem:
    """TRD §5.1 WorkItem — WBS Task 또는 Feature 하나를 표현한다.

    ``kind``: ``"wbs"`` | ``"feat"``.
    """

    id: str
    kind: str
    title: Optional[str]
    path: str
    status: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    elapsed_seconds: Optional[float]
    bypassed: bool
    bypassed_reason: Optional[str]
    last_event: Optional[str]
    last_event_at: Optional[str]
    phase_history_tail: List[PhaseEntry] = field(default_factory=list)
    wp_id: Optional[str] = None
    depends: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _cap_error(text: Optional[str]) -> str:
    """error 문자열을 ``_ERROR_CAP`` 바이트 이내로 제한한다."""
    if text is None:
        return ""
    if len(text) <= _ERROR_CAP:
        return text
    return text[:_ERROR_CAP]


def _read_state_json(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """state.json 을 1MB 가드와 함께 읽어 ``(dict|None, error|None)`` 을 반환한다.

    실패 경로:

    - 크기 초과 → ``(None, "file too large: {size} bytes")``
    - stat/OSError → ``(None, "stat error: ...")`` 또는 ``"read error: ..."``
    - JSON 파싱 실패 → ``(None, 원문 앞 500B)``
    - dict 가 아닌 최상위 타입 → ``(None, "unexpected type: ...")``
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, _cap_error(f"stat error: {exc}")

    if size > _MAX_STATE_BYTES:
        return None, _cap_error(f"file too large: {size} bytes")

    try:
        with open(path, "r", encoding="utf-8") as fp:
            raw = fp.read()
    except OSError as exc:
        return None, _cap_error(f"read error: {exc}")

    try:
        data = json.loads(raw)
    except ValueError:
        # JSON 파싱 실패 — 원문 앞 500B를 그대로 담아 디버깅을 돕는다.
        return None, _cap_error(raw if raw else "json error")

    if not isinstance(data, dict):
        return None, _cap_error(f"unexpected type: {type(data).__name__}")

    return data, None


def _normalize_elapsed(value) -> Optional[float]:
    """Return *value* if it is numeric (int/float, not bool), else None.

    Centralises the defensive coercion used for both ``state.json.elapsed_seconds``
    and ``phase_history[*].elapsed_seconds`` so both call sites share one rule.
    ``bool`` is excluded because ``isinstance(True, int) is True`` in Python, and a
    state.json serialising a boolean into this slot is almost certainly corrupt.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _build_phase_history_tail(history) -> List[PhaseEntry]:
    """phase_history[-10:] 를 ``PhaseEntry`` 리스트로 변환. 비정상 원소는 스킵."""
    if not isinstance(history, list):
        return []
    result: List[PhaseEntry] = []
    for entry in history[-_PHASE_TAIL_LIMIT:]:
        if not isinstance(entry, dict):
            continue
        result.append(PhaseEntry(
            event=entry.get("event"),
            from_status=entry.get("from"),
            to_status=entry.get("to"),
            at=entry.get("at"),
            elapsed_seconds=_normalize_elapsed(entry.get("elapsed_seconds")),
        ))
    return result


_WBS_WP_RE = re.compile(r"^##\s+(WP-[\w-]+)\s*:", re.MULTILINE)
_WBS_TSK_RE = re.compile(r"^###\s+(TSK-[\w-]+)\s*:\s*(.+?)\s*$", re.MULTILINE)


def _load_wbs_title_map(docs_dir: Path):
    """docs_dir/wbs.md 를 한 번 읽어 ``{TSK-ID: (title, wp_id, depends)}`` 반환.

    파싱 실패(파일 없음/IO 오류/크기 초과)는 조용히 빈 맵 fallback.
    """
    wbs_path = docs_dir / "wbs.md"
    try:
        size = wbs_path.stat().st_size
    except OSError:
        return {}
    # wbs.md는 여러 Task 설명이 들어가므로 state.json 한도(1MB)의 4배까지 허용.
    if size > _MAX_STATE_BYTES * 4:
        return {}
    try:
        with open(wbs_path, "r", encoding="utf-8") as fp:
            text = fp.read()
    except OSError:
        return {}

    result = {}
    current_wp: Optional[str] = None
    current_tsk: Optional[str] = None
    current_title: Optional[str] = None
    current_depends: List[str] = []

    def _commit(tsk, title, wp, depends):
        if tsk:
            result[tsk] = (title, wp, depends)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m_wp = _WBS_WP_RE.match(line)
        if m_wp:
            _commit(current_tsk, current_title, current_wp, current_depends)
            current_wp = m_wp.group(1)
            current_tsk = None
            current_title = None
            current_depends = []
            continue
        m_tsk = _WBS_TSK_RE.match(line)
        if m_tsk:
            _commit(current_tsk, current_title, current_wp, current_depends)
            current_tsk = m_tsk.group(1)
            current_title = m_tsk.group(2).strip() or None
            current_depends = []
            continue
        stripped = line.lstrip()
        if stripped.startswith("- depends:"):
            rest = stripped[len("- depends:"):].strip()
            if rest in ("", "-"):
                current_depends = []
            else:
                current_depends = [
                    token.strip() for token in rest.split(",") if token.strip()
                ]
    _commit(current_tsk, current_title, current_wp, current_depends)
    return result


def _load_feature_title(feat_dir: Path) -> Optional[str]:
    """feat_dir/spec.md 의 첫 non-empty 라인을 title로 반환. 실패 시 None."""
    spec_path = feat_dir / "spec.md"
    try:
        size = spec_path.stat().st_size
    except OSError:
        return None
    if size > _MAX_STATE_BYTES:
        return None
    try:
        with open(spec_path, "r", encoding="utf-8", errors="replace") as fp:
            for raw_line in fp:
                candidate = raw_line.strip()
                if candidate:
                    return candidate
    except OSError:
        return None
    return None


def _make_workitem_from_error(
    item_id: str, kind: str, abs_path: str, error: str,
    wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    return WorkItem(
        id=item_id, kind=kind, title=None, path=abs_path,
        status=None, started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=False, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id, depends=list(depends),
        error=error,
    )


def _make_workitem_from_state(
    item_id: str, kind: str, abs_path: str, data: dict,
    title: Optional[str], wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    last_block = data.get("last")
    if not isinstance(last_block, dict):
        last_block = {}
    return WorkItem(
        id=item_id,
        kind=kind,
        title=title,
        path=abs_path,
        status=data.get("status"),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        elapsed_seconds=_normalize_elapsed(data.get("elapsed_seconds")),
        bypassed=bool(data.get("bypassed", False)),
        bypassed_reason=data.get("bypassed_reason"),
        last_event=last_block.get("event"),
        last_event_at=last_block.get("at"),
        phase_history_tail=_build_phase_history_tail(data.get("phase_history")),
        wp_id=wp_id,
        depends=list(depends),
        error=None,
    )


def _resolve_abs_path(path: Path) -> str:
    """Return ``str(path.resolve())``, falling back to ``str(path)`` on OSError.

    ``resolve()`` can raise on FIFO/socket nodes or broken symlinks — the scan
    loop must never abort mid-iteration, so we degrade to the raw path string.
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


# Lookup callable signature: (item_id, state_path) -> (title, wp_id, depends)
# Used by ``_scan_dir`` so ``scan_tasks`` and ``scan_features`` can share the
# filesystem-walking skeleton while supplying their own metadata sources.


def _scan_dir(docs_dir: Path, subdir: str, kind: str, lookup) -> List[WorkItem]:
    """Walk ``{docs_dir}/{subdir}/*/state.json`` and build ``WorkItem`` list.

    Common skeleton for ``scan_tasks`` (kind="wbs") and ``scan_features``
    (kind="feat"). Per-kind metadata is resolved via the ``lookup`` callable so
    the iteration/error-handling pattern stays in one place.
    """
    docs_dir = Path(docs_dir)
    root = docs_dir / subdir
    if not root.is_dir():
        return []

    items: List[WorkItem] = []
    for state_path in sorted(root.glob("*/state.json")):
        item_id = state_path.parent.name
        abs_path = _resolve_abs_path(state_path)
        title, wp_id, depends = lookup(item_id, state_path)
        data, err = _read_state_json(state_path)
        if err is not None:
            items.append(_make_workitem_from_error(
                item_id, kind, abs_path, err, wp_id, depends,
            ))
            continue
        items.append(_make_workitem_from_state(
            item_id, kind, abs_path, data, title, wp_id, depends,
        ))
    return items


def scan_tasks(docs_dir: Path) -> List[WorkItem]:
    """``{docs_dir}/tasks/*/state.json`` 을 순회하며 ``WorkItem`` 리스트를 반환.

    - tasks 디렉터리가 없으면 ``[]`` 반환 (예외 없음).
    - 파싱 실패한 state.json 은 ``error`` 가 채워진 ``WorkItem`` 으로 반환.
    - wbs.md 가 있으면 title/wp_id/depends 를 함께 채운다 (1회 파싱).
    """
    docs_dir = Path(docs_dir)
    title_map = _load_wbs_title_map(docs_dir) if (docs_dir / "tasks").is_dir() else {}

    def _task_lookup(item_id, _state_path):
        return title_map.get(item_id, (None, None, []))

    return _scan_dir(docs_dir, "tasks", "wbs", _task_lookup)


def scan_features(docs_dir: Path) -> List[WorkItem]:
    """``{docs_dir}/features/*/state.json`` 을 순회하며 ``WorkItem`` 리스트를 반환.

    - features 디렉터리가 없으면 ``[]`` 반환.
    - title 은 개별 feature 의 ``spec.md`` 첫 non-empty 줄에서 얻는다.
    - ``wp_id=None``, ``depends=[]`` 고정 — feature 는 WBS 의존성 매핑이 없다.
    """
    def _feat_lookup(_item_id, state_path):
        return _load_feature_title(state_path.parent), None, []

    return _scan_dir(docs_dir, "features", "feat", _feat_lookup)


# ---------------------------------------------------------------------------
# --- end scan functions ---
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTML dashboard rendering (TSK-01-04)
# ---------------------------------------------------------------------------

_DEFAULT_REFRESH_SECONDS = 3
_PHASES_SECTION_LIMIT = 10
_ERROR_TITLE_CAP = 200
_SECTION_ANCHORS = ("wbs", "features", "team", "subagents", "phases")

# Mapping from agent-pool signal ``kind`` to badge CSS class. Module-level so
# the ``_section_subagents`` loop does not rebuild the dict per row.
_SUBAGENT_BADGE_CSS = {
    "running": "badge-run",
    "done": "badge-xx",
    "failed": "badge-fail",
    "bypassed": "badge-bypass",
}

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
:root {
  --bg: #0d1117;
  --fg: #e6edf3;
  --muted: #8b949e;
  --border: #30363d;
  --panel: #161b22;
  --accent: #58a6ff;
  --warn: #f85149;
  --blue: #388bfd;
  --purple: #bc8cff;
  --green: #3fb950;
  --gray: #8b949e;
  --orange: #d29922;
  --red: #f85149;
  --yellow: #e3b341;
  --light-gray: #6e7681;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 1.25rem 1.5rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.5;
}
h1 { font-size: 1.25rem; margin: 0 0 0.5rem; }
h2 { font-size: 1.05rem; margin: 0 0 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
dl.meta { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1rem; margin: 0; }
dl.meta dt { color: var(--muted); }
dl.meta dd { margin: 0; }
.top-nav { margin: 0.5rem 0 1rem; padding: 0.25rem 0; border-bottom: 1px solid var(--border); }
.top-nav a { color: var(--accent); margin-right: 1rem; text-decoration: none; }
.top-nav a:hover { text-decoration: underline; }
section { background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
details { margin-bottom: 0.5rem; }
details summary { cursor: pointer; color: var(--accent); font-weight: 600; padding: 0.25rem 0; }
.task-row { display: grid; grid-template-columns: 9rem 8rem 1fr 6rem 4rem 1.5rem; gap: 0.5rem; align-items: center; padding: 0.25rem 0.5rem; border-bottom: 1px dashed var(--border); font-size: 0.92rem; }
.task-row:last-child { border-bottom: none; }
.task-row .id { color: var(--muted); font-family: "SFMono-Regular", Consolas, monospace; }
.task-row .title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-row .elapsed, .task-row .retry { color: var(--muted); font-size: 0.85rem; font-family: "SFMono-Regular", Consolas, monospace; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 10px; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em; }
.badge-dd { background: rgba(56,139,253,0.15); color: var(--blue); border: 1px solid var(--blue); }
.badge-im { background: rgba(188,140,255,0.15); color: var(--purple); border: 1px solid var(--purple); }
.badge-ts { background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid var(--green); }
.badge-xx { background: rgba(139,148,158,0.15); color: var(--gray); border: 1px solid var(--gray); }
.badge-run { background: rgba(210,153,34,0.15); color: var(--orange); border: 1px solid var(--orange); animation: pulse 1.5s ease-in-out infinite; }
.badge-fail { background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid var(--red); }
.badge-bypass { background: rgba(227,179,65,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
.badge-pending { background: rgba(110,118,129,0.15); color: var(--light-gray); border: 1px solid var(--light-gray); }
.badge-warn { background: rgba(210,153,34,0.2); color: var(--orange); border: 1px solid var(--warn); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
.warn { color: var(--warn); font-weight: 600; }
.empty { color: var(--muted); font-style: italic; }
.info { color: var(--muted); font-size: 0.9rem; }
.pane-link { color: var(--accent); text-decoration: none; margin-left: 0.5rem; }
.pane-link:hover { text-decoration: underline; }
.pane-row { padding: 0.25rem 0.5rem; border-bottom: 1px dashed var(--border); font-size: 0.9rem; }
.pane-row:last-child { border-bottom: none; }
ol.phase-list { margin: 0; padding-left: 1.25rem; }
ol.phase-list li { margin-bottom: 0.25rem; font-size: 0.88rem; font-family: "SFMono-Regular", Consolas, monospace; }
"""


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


def _signal_set(signals: Optional[Iterable], kind: str) -> set:
    """Return set of task_ids for signals whose ``kind`` matches."""
    if not signals:
        return set()
    result = set()
    for sig in signals:
        sig_kind = getattr(sig, "kind", None)
        sig_task = getattr(sig, "task_id", None)
        if sig_kind == kind and sig_task:
            result.add(sig_task)
    return result


def _format_elapsed(item) -> str:
    """Return HH:MM:SS if elapsed_seconds is numeric, else ``"-"``."""
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
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _retry_count(item) -> int:
    """Count ``*.fail`` events in phase_history_tail."""
    tail = getattr(item, "phase_history_tail", None) or []
    count = 0
    for entry in tail:
        event = getattr(entry, "event", None)
        if isinstance(event, str) and event.endswith(".fail"):
            count += 1
    return count


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


def _section_wrap(anchor: str, heading: str, body: str) -> str:
    """Return a standard ``<section id="{anchor}">`` block with <h2> and body."""
    return (
        f'<section id="{anchor}">\n  <h2>{heading}</h2>\n'
        f'{body}\n'
        '</section>'
    )


def _empty_section(anchor: str, heading: str, message: str, css: str = "empty") -> str:
    """Render a standard empty-state section (``.empty`` or ``.info`` variant)."""
    return _section_wrap(anchor, heading, f'  <p class="{css}">{message}</p>')


def _section_header(model: dict) -> str:
    """Header section: project meta + top navigation (orphan-endpoint guard)."""
    generated_at = _esc(model.get("generated_at"))
    project_root = _esc(model.get("project_root"))
    docs_dir = _esc(model.get("docs_dir"))
    nav_links = "\n    ".join(
        f'<a href="#{anchor}">{anchor.title()}</a>' for anchor in _SECTION_ANCHORS
    )
    return (
        '<section id="header">\n'
        '  <h1>dev-plugin Monitor</h1>\n'
        '  <dl class="meta">\n'
        f'    <dt>generated_at</dt><dd>{generated_at}</dd>\n'
        f'    <dt>project_root</dt><dd>{project_root}</dd>\n'
        f'    <dt>docs_dir</dt><dd>{docs_dir}</dd>\n'
        '  </dl>\n'
        '  <nav class="top-nav">\n'
        f'    {nav_links}\n'
        '  </nav>\n'
        '</section>'
    )


def _render_task_row(item, running_ids: set, failed_ids: set) -> str:
    """Render a single <div class="task-row"> for a WorkItem.

    The row always has 6 cells (id, status|warn, title, elapsed, retry, flag).
    When ``error`` is present the status cell becomes a ⚠ badge-warn span; all
    other cells stay identical between the two branches.
    """
    item_id = getattr(item, "id", None)
    is_running = item_id in running_ids if item_id else False
    is_failed = item_id in failed_ids if item_id else False
    bypassed = bool(getattr(item, "bypassed", False))
    status = getattr(item, "status", None)
    error = getattr(item, "error", None)
    title = getattr(item, "title", None)

    id_html = f'<span class="id">{_esc(item_id)}</span>'
    title_html = f'<span class="title">{_esc(title) if title else ""}</span>'
    elapsed_html = f'<span class="elapsed">{_esc(_format_elapsed(item))}</span>'
    retry_html = f'<span class="retry">×{_retry_count(item)}</span>'
    flag_html = '<span title="bypassed">🟡</span>' if bypassed else '<span></span>'

    if error:
        error_preview = _esc(str(error)[:_ERROR_TITLE_CAP])
        status_cell = (
            f'<span class="badge badge-warn" title="{error_preview}">⚠ state error</span>'
        )
    else:
        status_cell = _status_badge(status, bypassed, is_running, is_failed)

    return (
        '<div class="task-row">\n'
        f'  {id_html}\n  {status_cell}\n  {title_html}\n'
        f'  {elapsed_html}\n  {retry_html}\n  {flag_html}\n'
        '</div>'
    )


def _section_wbs(tasks, running_ids: set, failed_ids: set) -> str:
    """WBS section: tasks grouped by WP (<details> per WP)."""
    if not tasks:
        return _empty_section("wbs", "WBS Tasks", "no tasks found — docs/tasks/ is empty")

    groups, order = _group_preserving_order(
        tasks, lambda item: getattr(item, "wp_id", None) or "WP-unknown"
    )

    blocks: List[str] = []
    for wp in order:
        rows = "\n".join(
            _render_task_row(item, running_ids, failed_ids) for item in groups[wp]
        )
        blocks.append(
            '<details open>\n'
            f'  <summary>{_esc(wp)} ({len(groups[wp])} tasks)</summary>\n'
            f'{rows}\n'
            '</details>'
        )

    return _section_wrap("wbs", "WBS Tasks", "\n".join(blocks))


def _section_features(features, running_ids: set, failed_ids: set) -> str:
    """Feature section: same rendering as tasks, flat list (no WP grouping)."""
    if not features:
        return _empty_section(
            "features", "Features", "no features found — docs/features/ is empty"
        )
    rows = "\n".join(
        _render_task_row(item, running_ids, failed_ids) for item in features
    )
    return _section_wrap("features", "Features", rows)


def _pane_attr(pane, key: str, default=""):
    """Read ``key`` from a PaneInfo dataclass *or* its ``asdict`` dict form.

    ``_build_state_snapshot`` coerces panes via ``_asdict_or_none`` so the
    dashboard model receives ``list[dict]``; unit tests pass raw dataclasses.
    Support both so the renderer doesn't silently emit empty fields.
    """
    if isinstance(pane, dict):
        return pane.get(key, default)
    return getattr(pane, key, default)


def _render_pane_row(pane) -> str:
    """Render a single ``<div class="pane-row">`` for a tmux pane."""
    pane_id_esc = _esc(_pane_attr(pane, "pane_id", ""))
    pane_idx = _esc(_pane_attr(pane, "pane_index", ""))
    cmd = _esc(_pane_attr(pane, "pane_current_command", ""))
    pid = _esc(_pane_attr(pane, "pane_pid", ""))
    return (
        '<div class="pane-row">\n'
        f'  <span class="id">{pane_id_esc}</span>'
        f' <span class="elapsed">#{pane_idx} {cmd} (pid {pid})</span>'
        f' <a class="pane-link" href="/pane/{pane_id_esc}">[show output]</a>\n'
        '</div>'
    )


def _section_team(panes) -> str:
    """Team section: tmux panes + pane-output entry links (orphan-endpoint guard)."""
    if panes is None:
        return _empty_section(
            "team",
            "Team Agents (tmux)",
            "tmux not available on this host — Team section shows no data,"
            " other sections work normally.",
            css="info",
        )
    if not panes:
        return _empty_section("team", "Team Agents (tmux)", "no tmux panes running")

    groups, order = _group_preserving_order(
        panes, lambda pane: _pane_attr(pane, "window_name", None) or "(unnamed)"
    )

    blocks: List[str] = []
    for window_name in order:
        rows = "\n".join(_render_pane_row(pane) for pane in groups[window_name])
        blocks.append(
            '<details open>\n'
            f'  <summary>{_esc(window_name)} ({len(groups[window_name])} panes)</summary>\n'
            f'{rows}\n'
            '</details>'
        )

    return _section_wrap("team", "Team Agents (tmux)", "\n".join(blocks))


_SUBAGENT_INFO = (
    '<p class="info">agent-pool subagents run inside the parent Claude session'
    ' — output capture is unavailable (signals only).</p>'
)


def _render_subagent_row(sig) -> str:
    """Render a single agent-pool slot row."""
    kind = getattr(sig, "kind", "")
    task_id = getattr(sig, "task_id", "")
    mtime = getattr(sig, "mtime", "")
    css = _SUBAGENT_BADGE_CSS.get(kind, "badge-pending")
    return (
        '<div class="pane-row">\n'
        f'  <span class="id">{_esc(task_id)}</span>'
        f' <span class="badge {css}">{_esc(kind if kind else "?")}</span>'
        f' <span class="elapsed">{_esc(mtime)}</span>\n'
        '</div>'
    )


def _section_subagents(signals) -> str:
    """Subagent section: agent-pool signal slots grouped by scope."""
    if not signals:
        return _section_wrap(
            "subagents",
            "Subagents (agent-pool)",
            f'  {_SUBAGENT_INFO}\n  <p class="empty">no agent-pool signals</p>',
        )

    groups, order = _group_preserving_order(
        signals, lambda sig: getattr(sig, "scope", None) or "agent-pool:unknown"
    )

    blocks: List[str] = []
    for scope in order:
        rows = "\n".join(_render_subagent_row(sig) for sig in groups[scope])
        blocks.append(
            '<details open>\n'
            f'  <summary>{_esc(scope)} ({len(groups[scope])} slots)</summary>\n'
            f'{rows}\n'
            '</details>'
        )

    return _section_wrap(
        "subagents",
        "Subagents (agent-pool)",
        f'  {_SUBAGENT_INFO}\n{chr(10).join(blocks)}',
    )


def _section_phase_history(tasks, features) -> str:
    """Phase-history section: most recent events across tasks+features (cap 10)."""
    collected: list = []
    for item in list(tasks or []) + list(features or []):
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            collected.append((getattr(item, "id", "?"), entry))

    collected.sort(key=lambda pair: getattr(pair[1], "at", "") or "", reverse=True)
    top = collected[:_PHASES_SECTION_LIMIT]

    if not top:
        return _empty_section("phases", "Recent Phase History", "no phase history yet")

    items = []
    for item_id, entry in top:
        at = _esc(getattr(entry, "at", ""))
        event = _esc(getattr(entry, "event", ""))
        from_s = _esc(getattr(entry, "from_status", ""))
        to_s = _esc(getattr(entry, "to_status", ""))
        elapsed = getattr(entry, "elapsed_seconds", None)
        elapsed_str = _esc(elapsed if elapsed is not None else "-")
        items.append(
            f'  <li>{at} · {_esc(item_id)} · {event} · {from_s} → {to_s}'
            f' · {elapsed_str}s</li>'
        )

    return _section_wrap(
        "phases",
        "Recent Phase History",
        '  <ol class="phase-list">\n' + "\n".join(items) + "\n  </ol>",
    )


def render_dashboard(model: dict) -> str:
    """Render the full monitor dashboard HTML document (TSK-01-04).

    See ``docs/monitor/tasks/TSK-01-04/design.md`` for the full contract. All
    user-derived strings flow through ``html.escape`` (via ``_esc``) before
    being concatenated into the output. No external CDN/font/script is
    referenced — only inline CSS.

    The returned string is a complete ``<!DOCTYPE html>`` document. The
    ``MonitorHandler`` (future TSK-01-01 integration) is expected to UTF-8
    encode the bytes and serve them with ``Content-Type: text/html; charset=utf-8``.
    """
    if not isinstance(model, dict):
        model = {}

    refresh = _refresh_seconds(model)
    shared_signals = model.get("shared_signals") or []
    running_ids = _signal_set(shared_signals, "running")
    failed_ids = _signal_set(shared_signals, "failed")

    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []

    sections = [
        _section_header(model),
        _section_wbs(tasks, running_ids, failed_ids),
        _section_features(features, running_ids, failed_ids),
        _section_team(model.get("tmux_panes")),
        _section_subagents(model.get("agent_pool_signals") or []),
        _section_phase_history(tasks, features),
    ]
    body = "\n".join(sections)

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        f'  <meta http-equiv="refresh" content="{refresh}">\n'
        '  <title>dev-plugin Monitor</title>\n'
        f'  <style>{DASHBOARD_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        f'{body}\n'
        '</body>\n'
        '</html>\n'
    )


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

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        f'  <title>pane {escaped_id}</title>\n'
        f'  <style>{_PANE_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        '<nav class="top-nav"><a href="/">&#x2190; back to dashboard</a></nav>\n'
        f'<h1>pane <code>{escaped_id}</code></h1>\n'
        f'{error_block}'
        f'<pre class="pane-capture" data-pane="{escaped_id}">{escaped_lines}</pre>\n'
        f'<div class="footer">captured at {escaped_ts}</div>\n'
        f'<script>{_PANE_JS}</script>\n'
        '</body>\n'
        '</html>\n'
    )


def _render_pane_json(payload: dict) -> bytes:
    """Serialize the pane payload dict to UTF-8 JSON bytes.

    ``line_count`` is always present (acceptance §3).
    """
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _send_html_response(handler, status: int, body_str: str) -> None:
    """Write a text/html; charset=utf-8 response to *handler*."""
    body = body_str.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _handle_pane_html(
    handler,
    pane_id: str,
    *,
    capture: Callable[[str], str] = capture_pane,
    max_lines: Optional[int] = None,
) -> None:
    """Handle ``GET /pane/{pane_id}`` — respond with HTML.

    - Invalid pane_id → 400 HTML error page.
    - Subprocess failure (any returncode) → 200 HTML with error message.
    - tmux binary missing (FileNotFoundError) → 200 HTML with 'tmux not available'.
    """
    if max_lines is None:
        server_obj = getattr(handler, "server", None)
        max_lines = int(getattr(server_obj, "max_pane_lines", _DEFAULT_MAX_PANE_LINES))

    try:
        payload = _pane_capture_payload(pane_id, capture, max_lines=max_lines)
    except ValueError:
        error_html = (
            '<!DOCTYPE html><html><body>'
            '<div class="error">invalid pane id</div>'
            '</body></html>'
        )
        _send_html_response(handler, 400, error_html)
        return

    html_body = _render_pane_html(pane_id, payload)
    _send_html_response(handler, 200, html_body)


def _handle_pane_api(
    handler,
    pane_id: str,
    *,
    capture: Callable[[str], str] = capture_pane,
    max_lines: Optional[int] = None,
) -> None:
    """Handle ``GET /api/pane/{pane_id}`` — respond with JSON.

    - Invalid pane_id → 400 JSON ``{"error":"invalid pane id","code":400}``.
    - Subprocess failure → 200 JSON with ``error`` field; ``line_count`` always present.
    """
    if max_lines is None:
        server_obj = getattr(handler, "server", None)
        max_lines = int(getattr(server_obj, "max_pane_lines", _DEFAULT_MAX_PANE_LINES))

    try:
        payload = _pane_capture_payload(pane_id, capture, max_lines=max_lines)
    except ValueError:
        _json_error(handler, 400, "invalid pane id")
        return

    body = _render_pane_json(payload)
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# /api/state JSON snapshot endpoint (TSK-01-06)
# ---------------------------------------------------------------------------

_API_STATE_PATH = "/api/state"
_AGENT_POOL_SCOPE_PREFIX = "agent-pool:"


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


def _now_iso_z() -> str:
    """Current UTC time as ISO-8601 with ``Z`` suffix (seconds precision).

    Example: ``"2026-04-30T10:30:00Z"``. Matches the ``generated_at`` contract
    in TRD §4.1.
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


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


def _build_render_state(
    project_root: str,
    docs_dir: str,
    scan_tasks: Callable[[Any], List[WorkItem]],
    scan_features: Callable[[Any], List[WorkItem]],
    scan_signals: Callable[[], List[SignalEntry]],
    list_tmux_panes: Callable[[], Optional[List[PaneInfo]]],
) -> dict:
    """Collect state with raw dataclass instances intact (for HTML rendering).

    The HTML renderer (``render_dashboard`` and ``_section_*`` / ``_render_*``
    helpers) accesses fields via ``getattr(item, "id")``, so list items must
    remain dataclass instances — routing through :func:`_asdict_or_none` would
    convert them to ``dict`` and break every ``getattr`` call (regression
    found by TSK-03-02 QA retest: task-row id/title/status spans rendered as
    empty strings because ``getattr(dict, "id")`` returns ``None``).

    Returns a dict with the same 8 keys as :func:`_build_state_snapshot` but
    list entries remain as ``WorkItem`` / ``SignalEntry`` / ``PaneInfo``
    dataclass instances.
    """
    tasks = list(scan_tasks(docs_dir) or [])
    features = list(scan_features(docs_dir) or [])
    shared_signals, agent_pool_signals = _classify_signal_scopes(
        scan_signals() or []
    )
    panes = list_tmux_panes()

    return {
        "generated_at": _now_iso_z(),
        "project_root": project_root or "",
        "docs_dir": docs_dir or "",
        "wbs_tasks": tasks,
        "features": features,
        "shared_signals": shared_signals,
        "agent_pool_signals": agent_pool_signals,
        "tmux_panes": panes,
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
    """
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
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


def _handle_api_state(
    handler,
    *,
    scan_tasks: Callable[[Any], List[WorkItem]] = scan_tasks,  # type: ignore[assignment]
    scan_features: Callable[[Any], List[WorkItem]] = scan_features,  # type: ignore[assignment]
    scan_signals: Callable[[], List[SignalEntry]] = scan_signals,  # type: ignore[assignment]
    list_tmux_panes: Callable[[], Optional[List[PaneInfo]]] = list_tmux_panes,  # type: ignore[assignment]
) -> None:
    """Handle ``GET /api/state`` on *handler*.

    ``handler.server`` is expected to expose ``project_root`` / ``docs_dir``
    (the HTTP bootstrap — TSK-01-02 / TSK-01-01 — will wire these). Missing
    attributes degrade to empty strings so the endpoint still responds.

    All scanner exceptions are caught and mapped to a 500 JSON envelope; one
    line is logged to stderr so the server operator can see the failure.
    """
    try:
        payload = _build_state_snapshot(
            project_root=_server_attr(handler, "project_root"),
            docs_dir=_server_attr(handler, "docs_dir"),
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )
    except Exception as exc:  # 방어 계층 — 일반 경로 미도달
        sys.stderr.write(f"/api/state build failed: {exc!r}\n")
        _json_error(handler, 500, f"internal error: {exc!r}")
        return

    _json_response(handler, 200, payload)


# ---------------------------------------------------------------------------
# HTTP Handler & Server (TSK-01-01)
# ---------------------------------------------------------------------------


class MonitorHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dev-plugin monitor server.

    Routing:
        GET /              → HTML dashboard (render_dashboard)
        GET /api/state     → JSON snapshot (_handle_api_state)
        GET /pane/{id}     → HTML pane detail (_handle_pane_html)
        GET /api/pane/{id} → JSON pane payload (_handle_pane_api)
        GET <other>        → 404
        non-GET methods    → 405 Method Not Allowed

    Binding is always ``127.0.0.1`` (set by ThreadingMonitorServer).
    ``log_message`` is overridden to write only the request line to stderr
    and leave stdout untouched.
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Override: write request line to stderr only; leave stdout empty."""
        sys.stderr.write(f"{self.requestline}\n")

    # ------------------------------------------------------------------
    # Non-GET methods → 405
    # ------------------------------------------------------------------

    def _send_405(self) -> None:
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        self._send_405()

    def do_PUT(self) -> None:  # noqa: N802
        self._send_405()

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_405()

    def do_PATCH(self) -> None:  # noqa: N802
        self._send_405()

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_405()

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path

        if path == "/":
            self._route_root()
        elif _is_api_state_path(self.path):
            self._route_api_state()
        elif _is_pane_api_path(path):
            pane_id = path[len(_API_PANE_PATH_PREFIX):]
            _handle_pane_api(self, pane_id)
        elif _is_pane_html_path(path):
            pane_id = path[len(_PANE_PATH_PREFIX):]
            _handle_pane_html(self, pane_id)
        else:
            self._route_not_found()

    # ------------------------------------------------------------------
    # Route implementations
    # ------------------------------------------------------------------

    def _route_root(self) -> None:
        """GET / — build model dict and render dashboard HTML.

        Uses :func:`_build_render_state` (raw dataclass lists) instead of
        :func:`_build_state_snapshot` (dict lists) because the renderer
        accesses fields via ``getattr(item, "id")``; dict items would silently
        render as empty spans.
        """
        server = getattr(self, "server", None)
        refresh_seconds = int(getattr(server, "refresh_seconds", _DEFAULT_REFRESH_SECONDS))

        state = _build_render_state(
            project_root=_server_attr(self, "project_root"),
            docs_dir=_server_attr(self, "docs_dir"),
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )
        model = {**state, "refresh_seconds": refresh_seconds}
        html_body = render_dashboard(model)
        _send_html_response(self, 200, html_body)

    def _route_api_state(self) -> None:
        """GET /api/state — delegate to _handle_api_state."""
        _handle_api_state(self)

    def _route_not_found(self) -> None:
        """Unmatched GET path → 404."""
        body = b"404 Not Found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ThreadingMonitorServer(ThreadingHTTPServer):
    """ThreadingHTTPServer subclass that carries server-wide config attributes.

    Attributes injected by ``main()``:
        project_root (str): resolved project root path.
        docs_dir (str): docs directory path.
        max_pane_lines (int): scrollback line cap for pane capture.
        refresh_seconds (int): dashboard meta-refresh interval.
        no_tmux (bool): when True, tmux calls should be skipped.

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

    _setup_signal_handler(server, pid_path)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        cleanup_pid_file(pid_path)


if __name__ == "__main__":
    main()
