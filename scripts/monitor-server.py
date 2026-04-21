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

import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
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
_RAW_ERROR_CAP = 500


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
    raw_error: Optional[str] = None


def _cap_raw_error(text: str) -> str:
    """raw_error 문자열을 ``_RAW_ERROR_CAP`` 바이트 이내로 제한한다."""
    if text is None:
        return ""
    if len(text) <= _RAW_ERROR_CAP:
        return text
    return text[:_RAW_ERROR_CAP]


def _read_state_json(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """state.json 을 1MB 가드와 함께 읽어 ``(dict|None, raw_error|None)`` 을 반환한다.

    실패 경로:

    - 크기 초과 → ``(None, "file too large: {size} bytes")``
    - stat/OSError → ``(None, "stat error: ...")`` 또는 ``"read error: ..."``
    - JSON 파싱 실패 → ``(None, 원문 앞 500B)``
    - dict 가 아닌 최상위 타입 → ``(None, "unexpected type: ...")``
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, _cap_raw_error(f"stat error: {exc}")

    if size > _MAX_STATE_BYTES:
        return None, _cap_raw_error(f"file too large: {size} bytes")

    try:
        with open(path, "r", encoding="utf-8") as fp:
            raw = fp.read()
    except OSError as exc:
        return None, _cap_raw_error(f"read error: {exc}")

    try:
        data = json.loads(raw)
    except ValueError:
        # JSON 파싱 실패 — 원문 앞 500B를 그대로 담아 디버깅을 돕는다.
        return None, _cap_raw_error(raw if raw else "json error")

    if not isinstance(data, dict):
        return None, _cap_raw_error(f"unexpected type: {type(data).__name__}")

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
    item_id: str, kind: str, abs_path: str, raw_error: str,
    wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    return WorkItem(
        id=item_id, kind=kind, title=None, path=abs_path,
        status=None, started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=False, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id, depends=list(depends),
        raw_error=raw_error,
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
        raw_error=None,
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
    - 파싱 실패한 state.json 은 ``raw_error`` 가 채워진 ``WorkItem`` 으로 반환.
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
_RAW_ERROR_TITLE_CAP = 200
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
    When ``raw_error`` is present the status cell becomes a ⚠️ warn link; all
    other cells stay identical between the two branches.
    """
    item_id = getattr(item, "id", None)
    is_running = item_id in running_ids if item_id else False
    is_failed = item_id in failed_ids if item_id else False
    bypassed = bool(getattr(item, "bypassed", False))
    status = getattr(item, "status", None)
    raw_error = getattr(item, "raw_error", None)
    title = getattr(item, "title", None)

    id_html = f'<span class="id">{_esc(item_id)}</span>'
    title_html = f'<span class="title">{_esc(title) if title else ""}</span>'
    elapsed_html = f'<span class="elapsed">{_esc(_format_elapsed(item))}</span>'
    retry_html = f'<span class="retry">×{_retry_count(item)}</span>'
    flag_html = '<span title="bypassed">🟡</span>' if bypassed else '<span></span>'

    if raw_error:
        raw_preview = _esc(str(raw_error)[:_RAW_ERROR_TITLE_CAP])
        status_cell = (
            f'<span class="warn" title="{raw_preview}">⚠️ '
            f'<a href="#" class="raw-link" title="{raw_preview}">raw</a></span>'
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


def _render_pane_row(pane) -> str:
    """Render a single ``<div class="pane-row">`` for a tmux pane."""
    pane_id_esc = _esc(getattr(pane, "pane_id", ""))
    pane_idx = _esc(getattr(pane, "pane_index", ""))
    cmd = _esc(getattr(pane, "pane_current_command", ""))
    pid = _esc(getattr(pane, "pane_pid", ""))
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
        panes, lambda pane: getattr(pane, "window_name", None) or "(unnamed)"
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
        return [asdict(x) if is_dataclass(x) and not isinstance(x, type) else x for x in value]
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


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

    Signal scope classification:

    - ``scope == "shared"`` → ``shared_signals``
    - ``scope.startswith("agent-pool:")`` → ``agent_pool_signals``
    - anything else (unknown future scope) → ``shared_signals`` (conservative
      fallback so no entry is silently dropped)

    ``tmux_panes`` is preserved as ``None`` when the scanner signals "tmux not
    installed" so clients can distinguish it from the empty-list "no panes
    running" case (TSK-01-06 acceptance 2).
    """
    tasks = list(scan_tasks(docs_dir) or [])
    features = list(scan_features(docs_dir) or [])
    raw_signals = list(scan_signals() or [])
    panes = list_tmux_panes()

    shared_signals: List[SignalEntry] = []
    agent_pool_signals: List[SignalEntry] = []
    for sig in raw_signals:
        scope = getattr(sig, "scope", None) or ""
        if scope.startswith("agent-pool:"):
            agent_pool_signals.append(sig)
        else:
            # "shared" 및 미지의 scope 모두 보수적으로 shared 에 편입 — 드롭 금지.
            shared_signals.append(sig)

    generated_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    return {
        "generated_at": generated_at,
        "project_root": project_root or "",
        "docs_dir": docs_dir or "",
        "wbs_tasks": _asdict_or_none(tasks),
        "features": _asdict_or_none(features),
        "shared_signals": _asdict_or_none(shared_signals),
        "agent_pool_signals": _asdict_or_none(agent_pool_signals),
        "tmux_panes": _asdict_or_none(panes),
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
    project_root = getattr(getattr(handler, "server", None), "project_root", "") or ""
    docs_dir = getattr(getattr(handler, "server", None), "docs_dir", "") or ""

    try:
        payload = _build_state_snapshot(
            project_root=str(project_root),
            docs_dir=str(docs_dir),
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
# Entry point (skeleton — real CLI arrives with TSK-01-01)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover - skeleton placeholder
    # TSK-01-01 will replace this block with argparse + HTTPServer bootstrap.
    sys.stderr.write(
        "monitor-server.py: HTTP bootstrap not yet wired (TSK-01-01 pending).\n"
    )
    sys.exit(0)
