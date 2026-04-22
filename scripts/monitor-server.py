#!/usr/bin/env python3
"""dev-monitor HTTP 서버 (단일 파일).

주요 구성 요소:

- 시그널 스캐너: ``scan_signals()``
- tmux pane 스캐너: ``list_tmux_panes()``, ``capture_pane(pane_id)``
- 데이터 클래스: ``SignalEntry``, ``PaneInfo`` (TRD §5.2 / §5.3)
- HTTP 서버: ``MonitorHandler``, ``run_server()``
- 라우팅: ``/`` (대시보드), ``/pane/{id}`` (HTML), ``/api/pane/{id}`` (JSON),
  ``/api/state`` (전체 스냅샷)

구현 원칙:
- Python 3.8+ stdlib 전용 (``CLAUDE.md`` 규약)
- 모든 ``subprocess.run`` 은 ``shell=False`` 리스트 인자 + 명시 ``timeout``
- 모든 실패 경로(디렉터리 부재, tmux 부재, 서버 미기동, 잘못된 pane_id,
  subprocess 오류/타임아웃)는 정의된 반환 값으로 흡수 — 예외는
  ``capture_pane`` 의 pane_id 형식 위반(ValueError)만 허용
- pane_id URL 인코딩: 링크 생성 시 ``quote(pane_id, safe="")``, 라우터에서
  ``unquote(path_segment)`` 후 ``_PANE_ID_RE`` 검증
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
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlsplit


# ---------------------------------------------------------------------------
# i18n (TSK-02-02)
# ---------------------------------------------------------------------------

_I18N: dict = {
    "ko": {
        "work_packages": "작업 패키지",
        "features": "기능",
        "team_agents": "팀 에이전트 (tmux)",
        "subagents": "서브 에이전트 (agent-pool)",
        "live_activity": "실시간 활동",
        "phase_timeline": "단계 타임라인",
    },
    "en": {
        "work_packages": "Work Packages",
        "features": "Features",
        "team_agents": "Team Agents (tmux)",
        "subagents": "Subagents (agent-pool)",
        "live_activity": "Live Activity",
        "phase_timeline": "Phase Timeline",
    },
}


def _normalize_lang(lang: str) -> str:
    """lang 정규화 헬퍼. ko/en 이외의 값은 'ko'로 폴백."""
    return lang if lang in _I18N else "ko"


def _t(lang: str, key: str) -> str:
    """i18n 헬퍼. 미지원 lang은 'ko' fallback, 미지원 key는 key 자체 반환."""
    return _I18N[_normalize_lang(lang)].get(key, key)


# ---------------------------------------------------------------------------
# Constants
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

# Agent-pool signal directory prefix and scope prefix (scan_signals + _classify_signal_scopes).
_AGENT_POOL_DIR_PREFIX = "agent-pool-signals-"
_AGENT_POOL_SCOPE_PREFIX = "agent-pool:"

# TSK-01-01: WP-scoped signal task_id prefix pattern (e.g. "WP-01-").
_WP_SIGNAL_PREFIX_RE = re.compile(r"^WP-\d{2}-")


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
        scope: subdir 이름(``"proj-a"`` 등), ``"shared"`` (root 직하 파일 fallback),
        또는 ``"agent-pool:{timestamp}"``.
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

    - ``${TMPDIR}/claude-signals/{subdir}/**`` (recursive) →
      ``scope="{subdir}"`` (subdir name is the scope, TRD §3.3 subdir-per-scope).
    - ``${TMPDIR}/claude-signals/{bare-file}`` (root-direct file, no subdir) →
      ``scope="shared"`` (backward-compatibility fallback).
    - ``${TMPDIR}/agent-pool-signals-*/**`` (recursive) →
      ``scope="agent-pool:{timestamp}"`` where ``{timestamp}`` is the directory-name
      suffix after the ``agent-pool-signals-`` prefix (preserves the trailing
      ``-$$`` PID used by agent-pool).

    Note: ``_classify_signal_scopes`` treats any scope that is not prefixed with
    ``agent-pool:`` as the shared bucket (including subdir names), so the dashboard
    display count is unchanged regardless of the actual scope value.

    Files whose extension is not one of ``running``/``done``/``failed``/``bypassed``
    are silently skipped. Missing directories are not errors — they simply yield
    zero entries.
    """
    tmp_root = tempfile.gettempdir()
    entries: List[SignalEntry] = []

    # (A) Subdir-per-scope — iterate direct children of claude-signals/
    cs_root = os.path.join(tmp_root, "claude-signals")
    if os.path.isdir(cs_root):
        for child_name in sorted(os.listdir(cs_root)):
            child_path = os.path.join(cs_root, child_name)
            if os.path.isdir(child_path):
                # Directory: use child directory name as scope
                entries.extend(_walk_signal_entries(child_path, child_name))
            else:
                # Root-direct file: backward-compatibility fallback → scope="shared"
                entry = _signal_entry(child_path, "shared")
                if entry is not None:
                    entries.append(entry)

    # (B) Agent-pool scope — each agent-pool-signals-{timestamp}/ directory
    for pool_dir in glob.glob(os.path.join(tmp_root, f"{_AGENT_POOL_DIR_PREFIX}*")):
        pool_name = os.path.basename(pool_dir)
        timestamp = pool_name[len(_AGENT_POOL_DIR_PREFIX):]
        entries.extend(_walk_signal_entries(pool_dir, f"{_AGENT_POOL_SCOPE_PREFIX}{timestamp}"))

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
# --- subproject helpers (TSK-00-03) ---
# ---------------------------------------------------------------------------


def discover_subprojects(docs_dir: Path) -> List[str]:
    """``{docs_dir}/*/wbs.md`` 를 포함한 child 디렉터리 이름을 정렬된 리스트로 반환.

    - ``docs_dir`` 가 존재하지 않거나 디렉터리가 아니면 ``[]`` 반환 (예외 없음).
    - ``wbs.md`` 가 없는 child 디렉터리(예: ``tasks/``, ``features/``)는 제외.
    - 반환 리스트는 알파벳 오름차순 정렬 (결정론적 순서 보장).

    기존 ``args-parse.py:82-92`` 서브프로젝트 규약과 동일 — child 디렉터리에
    ``wbs.md`` 가 있으면 subproject로 판정한다. stdlib ``pathlib.Path`` 만 사용.
    """
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        return []
    return [
        child.name
        for child in sorted(docs_dir.iterdir())
        if child.is_dir() and (child / "wbs.md").is_file()
    ]


def _filter_by_subproject(state: dict, sp: str, project_name: str) -> dict:
    """``state`` dict를 in-place 수정하여 ``sp`` 서브프로젝트에 속하는 항목만 남긴다.

    필터 조건:

    **pane** (``state["tmux_panes"]`` 리스트, ``None`` 이면 ``None`` 그대로 유지):
    - ``window_name`` 이 ``-{sp}`` suffix 로 끝나거나
    - ``window_name`` 에 ``-{sp}-`` 가 포함되거나
    - ``pane_current_path`` 에 ``/{sp}/`` 가 포함되면 통과.

    **signal** (``state["signals"]`` 리스트):
    - ``scope`` 가 ``{project_name}-{sp}`` 와 정확히 일치하거나
    - ``scope`` 가 ``{project_name}-{sp}-`` 로 시작하면 통과.

    반환 값은 동일한 ``state`` dict (in-place 수정).
    """
    prefix = f"{project_name}-{sp}"
    prefix_dash = f"{prefix}-"
    suffix_marker = f"-{sp}"
    infix_marker = f"-{sp}-"
    path_marker = f"/{sp}/"

    # signals 필터
    signals = state.get("signals")
    if isinstance(signals, list):
        state["signals"] = [
            s for s in signals
            if isinstance(s, dict) and (
                s.get("scope") == prefix
                or (isinstance(s.get("scope"), str) and s["scope"].startswith(prefix_dash))
            )
        ]

    # pane 필터 — None 이면 그대로 유지
    panes = state.get("tmux_panes")
    if panes is not None and isinstance(panes, list):
        def _pane_matches(pane: dict) -> bool:
            wn = pane.get("window_name", "") or ""
            cwd = pane.get("pane_current_path", "") or ""
            return (
                wn.endswith(suffix_marker)
                or infix_marker in wn
                or path_marker in cwd
            )

        state["tmux_panes"] = [p for p in panes if isinstance(p, dict) and _pane_matches(p)]

    return state


# ---------------------------------------------------------------------------
# --- end scan functions ---
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTML dashboard rendering (TSK-01-04)
# ---------------------------------------------------------------------------

_DEFAULT_REFRESH_SECONDS = 3
_PHASES_SECTION_LIMIT = 10
_ERROR_TITLE_CAP = 200
_SECTION_ANCHORS = ("wp-cards", "features", "team", "subagents", "activity", "timeline", "phases")

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
}
button{ font: inherit; color: inherit; background:none; border:0; cursor:pointer; }
a{ color: inherit; }
summary{ cursor: pointer; list-style: none; }
summary::-webkit-details-marker{ display:none; }

/* ---------- layout shell ---------- */
.shell{
  position: relative;
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 20px 0;
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
  background: rgba(11,13,16,0.88);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
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
  width:8px; height:8px; border-radius: 50%;
  background: var(--done);
  animation: pulse 1.6s ease-out infinite;
}
@keyframes pulse{
  0%   { box-shadow: 0 0 0 0 rgba(78,208,138,.55); }
  70%  { box-shadow: 0 0 0 10px rgba(78,208,138,0);  }
  100% { box-shadow: 0 0 0 0 rgba(78,208,138,0);   }
}

.btn{
  display:inline-flex; align-items:center; gap: 8px;
  height: 28px; padding: 0 10px;
  background: var(--bg-2); border: 1px solid var(--line-2);
  color: var(--ink-2);
  border-radius: var(--radius);
  font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
  font-weight: 600;
}
.btn[aria-pressed="true"]{
  background: rgba(200,155,106,0.08);
  border-color: var(--accent-dim);
  color: var(--accent-hi);
}
.btn .led{
  width:6px; height:6px; border-radius:50%;
  background: var(--ink-4);
}
.btn[aria-pressed="true"] .led{
  background: var(--accent-hi);
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
  content:"\\25AE"; color: var(--accent); margin-right: 6px; opacity:.8;
}
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
.kpi .num{
  font-family: var(--mono);
  font-size: 38px; font-weight: 600; line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ink);
  align-self: end;
}
.kpi .spark{ grid-column: 1 / -1; height: 28px; margin-top: 6px; }
.kpi--run   .label .sw{ background: var(--run); }
.kpi--fail  .label .sw{ background: var(--fail); }
.kpi--bypass .label .sw{ background: var(--bypass); }
.kpi--done  .label .sw{ background: var(--done); }
.kpi--pend  .label .sw{ background: var(--pending); }
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
}
.chip .sw{ width:8px; height:8px; border-radius:50%; background: var(--ink-4); }
.chip[data-filter="running"] .sw{ background: var(--run); }
.chip[data-filter="failed"]  .sw{ background: var(--fail); }
.chip[data-filter="bypass"]  .sw{ background: var(--bypass); }
.chip[aria-pressed="true"]{
  background: var(--bg-2);
  border-color: var(--line-hi);
  color: var(--ink);
}

/* ---------- main 2-col grid ---------- */
.grid{
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 28px;
  padding-top: 8px;
}
.col{ min-width: 0; display:flex; flex-direction:column; gap: 0; }

/* ---------- 4. WP Cards ---------- */
.wp-stack{ display:flex; flex-direction:column; gap: 14px; }
.wp{
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
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
  font-size: var(--font-h2); font-weight: 600;
  color: var(--ink);
}
.wp-donut .pct small{ font-size: 9px; color: var(--ink-4); font-weight: 400; display:block; }

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
  white-space: nowrap;
}
.wp-title h3{
  margin: 0; font-weight: 500; font-size: var(--font-h2);
  color: var(--ink);
  font-family: var(--display);
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
.wp-meta .big{ color: var(--ink-2); font-size: 11px; display:block; }

.wp-tasks{ border-top: 1px solid var(--line); background: rgba(0,0,0,0.15); }
.wp-tasks > summary{
  padding: 10px 18px;
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--ink-3);
  display:flex; align-items:center; gap: 8px;
}
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
  min-height: 38px;
}
.trow:last-child{ border-bottom: 0; }

.trow .statusbar{
  align-self: stretch;
  width: 4px;
  background: var(--ink-4);
}
.trow[data-status="done"]    .statusbar{ background: var(--done); }
.trow[data-status="running"] .statusbar{ background: var(--run); }
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
.trow[data-status="done"] .badge{ color: var(--done); }
.trow[data-status="running"] .badge{ color: var(--run); }
.trow[data-status="failed"] .badge{ color: var(--fail); }
.trow[data-status="bypass"] .badge{ color: var(--bypass); }
.trow[data-status="pending"] .badge{ color: var(--pending); }
@keyframes breathe{ 0%,100%{ opacity:1; transform: scale(1);} 50%{ opacity: .55; transform: scale(.85);} }

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
.trow .flag.f-crit{ color: var(--fail); }
.trow .flag.f-new { color: var(--accent); }

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

.arow{
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 5px 14px;
  font-family: var(--mono);
  font-size: 11.5px;
  color: var(--ink-2);
  border-bottom: 1px dashed transparent;
}
.arow .t{ color: var(--ink-4); font-size: 11px; }
.arow .tid{ color: var(--ink); font-weight: 600; font-size: 11px; }
.arow .evt{ color: var(--ink-3); font-size: 11px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;}
.arow .evt .arrow{ color: var(--ink-4); margin: 0 4px; }
.arow .evt .from{ color: var(--ink-3); }
.arow .evt .to{ font-weight: 600; }
.arow[data-to="done"] .to{ color: var(--done); }
.arow[data-to="running"] .to{ color: var(--run); }
.arow[data-to="failed"] .to{ color: var(--fail); }
.arow[data-to="bypass"] .to{ color: var(--bypass); }
.arow[data-to="pending"] .to{ color: var(--pending); }
.arow .el{ color: var(--ink-4); font-size: 11px; }

/* ---------- 7. Phase Timeline ---------- */
.timeline{ padding: 8px 14px 14px; }
.timeline-head{
  display:flex; justify-content: space-between;
  font-size: 10px; color: var(--ink-4);
  letter-spacing: .1em; text-transform: uppercase;
  padding: 0 4px 8px;
}
.tl-row{
  display:grid;
  grid-template-columns: 82px 1fr;
  align-items: center;
  gap: 10px; padding: 3px 0; font-size: 11px;
}
.tl-row .lbl{ color: var(--ink-3); font-family: var(--mono); font-size: 10.5px; white-space:nowrap; }
.tl-track{
  position: relative; height: 14px;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 2px; overflow: hidden;
}
.tl-track .seg{ position: absolute; top:0; bottom:0; }
.tl-track .seg-done   { background: var(--done); }
.tl-track .seg-running{ background: var(--run); }
.tl-track .seg-failed { background: var(--fail); }
.tl-track .seg-bypass { background: var(--bypass); }
.tl-track .seg-pending{ background: var(--pending); }
.tl-track .seg-idle   { background: transparent; }

.tl-axis{ position: relative; height: 18px; margin-top: 6px; border-top: 1px solid var(--line); }
.tl-axis .tick{ position: absolute; top: 0; bottom: 10px; width: 1px; background: var(--line-2); }
.tl-axis .tick.major{ background: var(--line-hi); bottom: 6px;}
.tl-axis .tlabel{
  position:absolute; top: 4px; transform: translateX(-50%);
  font-family: var(--mono); font-size: 9.5px;
  color: var(--ink-4); white-space: nowrap;
}
.tl-now{ position:absolute; top:-2px; bottom:0; width: 1px; background: var(--accent); }

/* ---------- 8. Team Agents ---------- */
.team{ padding: 0; }
.pane{ border-bottom: 1px solid var(--line); }
.pane:last-child{ border-bottom: 0; }
.pane-head{
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 10px; align-items: center;
  padding: 10px 14px 8px;
}
.pane-head .name{
  font-family: var(--mono);
  font-size: 12px; font-weight: 600;
  color: var(--ink);
}
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
}
.mini-btn.primary{ border-color: var(--accent-dim); color: var(--accent-hi); }

.pane-preview{
  margin: 0 14px 12px;
  padding: 8px 10px;
  background: #07090c;
  border: 1px solid var(--line); border-radius: var(--radius);
  font-family: var(--mono); font-size: 11px; line-height: 1.5;
  color: var(--ink-2); white-space: pre-wrap; overflow-x: auto;
}

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
.sub[data-state="running"] .sw{ background: var(--run); animation: breathe 1.4s infinite;}
.sub[data-state="done"] .sw{ background: var(--done); }
.sub[data-state="failed"] .sw{ background: var(--fail); }
.sub .n{ color: var(--ink-4); font-size: 10px;}

/* ---------- 10. Phase history ---------- */
.history{
  margin-top: 28px; border: 1px solid var(--line);
  border-radius: var(--radius-lg); background: var(--bg-1); overflow: hidden;
}
.history table{ width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 11.5px; }
.history th, .history td{
  padding: 8px 14px; text-align: left;
  border-bottom: 1px solid var(--line); white-space: nowrap; color: var(--ink-2);
}
.history tbody tr:last-child td{ border-bottom: 0; }
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
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(3px);
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
.drawer-head h3{ margin: 0; font-family: var(--display); font-size: 16px; font-weight: 600; color: var(--ink); }
.drawer-head .meta{ color: var(--ink-3); font-size: 11px; margin-top: 4px; font-family: var(--mono); }
.drawer-close{
  width: 30px; height: 30px; border:1px solid var(--line-2);
  border-radius: 4px; display:grid; place-items:center; color: var(--ink-3);
}
.drawer-close:hover{ color: var(--fail); }

.drawer-status{
  display:flex; align-items:center; gap: 10px;
  padding: 10px 22px;
  font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ink-4); border-bottom: 1px solid var(--line); background: var(--bg);
}
.drawer-status .poll{ color: var(--done); display:inline-flex; align-items:center; gap: 6px;}

.drawer-pre{
  flex: 1; overflow: auto; margin: 0; padding: 16px 22px 22px;
  font-family: var(--mono); font-size: 12px; line-height: 1.55;
  color: var(--ink-2); background: #07090c; white-space: pre;
}

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
/* kpi-section: used by _section_kpi */
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


# v3 per-section eyebrow + aside metadata. Keys match section anchors.
_SECTION_EYEBROWS = {
    "wp-cards":   ("planning",    ""),
    "features":   ("unassigned",  ""),
    "activity":   ("stream",      'last 20 events · <b style="color:var(--done)">tailing</b>'),
    "timeline":   ("last 60 min", "tick: 15m"),
    "team":       ("tmux",        ""),
    "subagents":  ("agent-pool",  "fan-out / fan-in signals"),
    "phases":     ("audit",       "last 10 transitions"),
}


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
        f'<section id="{anchor}" data-section="{anchor}">\n'
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

    lang_toggle_html = (
        f'<nav class="lang-toggle">'
        f'<a href="{href_ko}">한</a>'
        f' <a href="{href_en}">EN</a>'
        f'</nav>\n'
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
        f'<span class="v" id="clock">{generated_at}</span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">interval</span>'
        f'<span class="v">{refresh_s}s</span></span>\n'
        '  </div>\n'
        '  <div class="actions">\n'
        f'    {lang_toggle_html}'
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
# TSK-01-02: KPI helpers + sticky header + KPI section
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
    - bypass_ids: items where item.bypassed is True
    - failed_ids: signal kind="failed", excluding bypass_ids
    - running_ids: signal kind="running", excluding bypass_ids and failed_ids
    - done_ids: signal kind="done", excluding bypass_ids, failed_ids, running_ids
    - pending: remainder
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
    raw_done = _signal_set(signals, "done")

    # Apply priority filter: each id is counted only in the highest-priority bucket
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
    """Render a v3 sparkline <svg class="spark"> from bucket counts.

    viewBox: '0 0 100 28' (reference design). When max_val==0 or len(buckets)<2
    renders a flat baseline. Includes <title> for screen reader accessibility.
    Emits both stroke polyline and a faint fill polygon to match reference.
    """
    n = len(buckets)
    if n == 0:
        buckets = [0]
        n = 1

    max_val = max(buckets)
    total = sum(buckets)
    title_text = f"sparkline: {total} events in last {n} minutes"

    if n < 2 or max_val == 0:
        points = "0,26 100,26"
        fill_points = ""
    else:
        step = 100.0 / max(n - 1, 1)
        pts = [f"{i*step:.1f},{28 - (24 * val / max_val):.1f}" for i, val in enumerate(buckets)]
        points = " ".join(pts)
        fill_points = points + " 100,28 0,28"

    fill_poly = (
        f'<polyline points="{fill_points}" fill="{color}" opacity="0.15" stroke="none"/>'
        if fill_points else ""
    )
    return (
        f'<svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">'
        f'<title>{_esc(title_text)}</title>'
        f'{fill_poly}'
        f'<polyline points="{points}" stroke="{color}" fill="none" stroke-width="1.4"/>'
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
        delta_n = sum(buckets)
        if delta_n > 0:
            delta_html = f'<span class="up">+{delta_n}</span> / 10m'
        else:
            delta_html = '<span>±0</span> / 10m'
        cards_html.append(
            f'<div class="kpi kpi--{suffix}" data-kpi="{kind}">\n'
            f'  <div class="label"><span class="sw"></span>{label}</div>\n'
            f'  <div class="num" aria-label="{label}: {n}">{n}</div>\n'
            f'  <div class="delta">{delta_html}</div>\n'
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
        f'<b style="color:var(--ink-2)">{total_items} items</b>'
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

    cx, cy, r = 20, 20, 16
    stroke_w = 6

    # Track circle (background)
    track = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" pathLength="100"'
        f' stroke="var(--line-2)" stroke-width="{stroke_w}"'
        ' fill="none" stroke-dasharray="100 0"/>'
    )

    if total == 0:
        return (
            '<svg viewBox="0 0 40 40" class="donut-svg">\n'
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
        # so pathLength="100" count is always track+4 = 5
        safe_pct = max(0, pct)
        dash = f"{safe_pct} {100 - safe_pct}"
        circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" pathLength="100"'
            f' stroke="{color}" stroke-width="{stroke_w}"'
            f' fill="none" stroke-dasharray="{dash}"'
            f' stroke-dashoffset="{-offset:.2f}"'
            ' transform="rotate(-90 20 20)"/>'
        )
        offset += safe_pct

    inner_html = "\n  ".join(circles)
    return (
        '<svg viewBox="0 0 40 40" class="donut-svg">\n'
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


def _render_task_row_v2(item, running_ids: set, failed_ids: set) -> str:
    """Render a v3 ``<div class="trow" data-status="{state}">`` row.

    Matches reference markup exactly — 7 ``<div>`` children:
    ``statusbar / tid / badge / ttitle / elapsed / retry / flags``.
    Badge text is lowercase (``running``/``done``/``failed``/``bypass``/``pending``)
    — reference design uses CSS to colour the pill.
    """
    item_id = getattr(item, "id", None)
    bypassed = bool(getattr(item, "bypassed", False))
    error = getattr(item, "error", None)
    title = getattr(item, "title", None)
    data_status = _trow_data_status(item, running_ids, failed_ids)

    badge_text = "error" if error else data_status
    badge_title_attr = ""
    if error:
        badge_title_attr = f' title="{_esc(str(error)[:_ERROR_TITLE_CAP])}"'

    # elapsed '00:00:00' and '-' are both unreadable in dense rows — show '—'
    elapsed_raw = _format_elapsed(item)
    if elapsed_raw in ("-", "00:00:00"):
        elapsed_display = "—"
    else:
        elapsed_display = elapsed_raw

    flags_inner = ""
    if bypassed:
        flags_inner = '<span class="flag f-crit">bypass</span>'

    clean_title = _esc(_clean_title(title))

    return (
        f'<div class="trow" data-status="{data_status}">\n'
        '  <div class="statusbar"></div>\n'
        f'  <div class="tid">{_esc(item_id)}</div>\n'
        f'  <div class="badge"{badge_title_attr}>{_esc(badge_text)}</div>\n'
        f'  <div class="ttitle">{clean_title}</div>\n'
        f'  <div class="elapsed">{_esc(elapsed_display)}</div>\n'
        f'  <div class="retry">×{_retry_count(item)}</div>\n'
        f'  <div class="flags">{flags_inner}</div>\n'
        '</div>'
    )


def _section_wp_cards(tasks, running_ids: set, failed_ids: set, heading: str = "Work Packages") -> str:
    """WP card section: tasks grouped by wp_id, each WP as a v3 .wp card.

    v3 structure per card:
    - <details class="wp"> with <summary><div class="wp-head">:
      - .wp-donut: SVG stroke-dasharray donut + .pct overlay
      - .wp-title: .id badge + h3 + .bar + .wp-counts
      - .wp-meta: total tasks count
    - <details class="wp-tasks"> body with .trow rows

    Empty tasks list → empty-state. Individual empty WP → empty-state per card.
    WP name XSS is escaped via ``_esc``.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    if not tasks:
        return _empty_section("wp-cards", heading, "no tasks found — docs/tasks/ is empty")

    groups, order = _group_preserving_order(
        tasks, lambda item: getattr(item, "wp_id", None) or "WP-unknown"
    )

    blocks: List[str] = []
    for wp in order:
        wp_tasks = groups[wp]
        counts = _wp_card_counts(wp_tasks, running_ids, failed_ids)
        total = len(wp_tasks)
        done_count = counts["done"]
        pct_done = round(done_count / total * 100) if total > 0 else 0

        # v3 donut SVG
        svg_html = _wp_donut_svg(counts)
        donut_html = (
            f'<div class="wp-donut" aria-label="{pct_done}% complete">\n'
            f'  {svg_html}\n'
            f'  <div class="pct">{pct_done}<small>%</small></div>\n'
            '</div>'
        )

        # progress bar (5-segment flex)
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

        wp_title_html = (
            '<div class="wp-title">\n'
            '  <div class="row1">\n'
            f'    <span class="id">{_esc(wp)}</span>\n'
            f'    <h3>{_esc(wp)}</h3>\n'
            '  </div>\n'
            f'  {bar_html}\n'
            f'  {counts_html}\n'
            '</div>'
        )

        wp_meta_html = f'<div class="wp-meta"><span class="big">{total} tasks</span></div>'

        wp_head_html = (
            '<div class="wp-head">\n'
            f'  {donut_html}\n'
            f'  {wp_title_html}\n'
            f'  {wp_meta_html}\n'
            '</div>'
        )

        if not wp_tasks:
            card_body_html = '<p class="empty">no tasks</p>'
        else:
            task_rows = "\n".join(
                _render_task_row_v2(item, running_ids, failed_ids) for item in wp_tasks
            )
            card_body_html = (
                '<details class="wp-tasks">\n'
                f'  <summary><span>Tasks</span> <span class="ct">({total})</span></summary>\n'
                f'  <div class="task-list">\n{task_rows}\n  </div>\n'
                '</details>'
            )

        blocks.append(
            f'<details class="wp" open data-wp="{_esc(wp)}">\n'
            '  <summary style="list-style:none; display:block;">\n'
            f'{wp_head_html}\n'
            '  </summary>\n'
            f'{card_body_html}\n'
            '</details>'
        )

    return _section_wrap("wp-cards", heading, "\n".join(blocks))


def _section_features(features, running_ids: set, failed_ids: set, heading: str = "Features") -> str:
    """Feature section: flat .trow list inside .features-wrap panel (no WP grouping).

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    if not features:
        return _empty_section(
            "features", heading, "no features found — docs/features/ is empty"
        )
    rows = "\n".join(
        _render_task_row_v2(item, running_ids, failed_ids) for item in features
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


def _pane_last_n_lines(pane_id: str, n: int = 3) -> str:
    """Return the last *n* non-blank lines from a tmux pane's scrollback.

    Calls ``capture_pane(pane_id)`` and strips trailing whitespace-only lines
    before taking the tail.  Returns an empty string on any error or when the
    result is entirely blank.
    """
    try:
        raw = capture_pane(pane_id)
    except Exception:
        return ""
    # rstrip removes trailing whitespace/newlines; splitlines() handles all
    # line-ending variants and produces no trailing empty element.
    lines = raw.rstrip().splitlines()
    if not lines:
        return ""
    return "\n".join(lines[-n:])


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
    pane_idx = _esc(_pane_attr(pane, "pane_index", ""))
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
        f'    <a class="mini-btn" href="/pane/{quote(pane_id_raw, safe="")}">show output</a>\n'
        f'    <button class="mini-btn primary" type="button"'
        f' data-pane-expand="{pane_id_esc}"'
        f' aria-label="Expand pane {pane_id_esc}">expand <span class="kbd">&#x21B5;</span></button>\n'
        f'  </div>\n'
        f'{preview_html}\n'
        '</div>'
    )


_TOO_MANY_PANES_THRESHOLD = 20


def _section_team(panes, heading: str = "Team Agents (tmux)") -> str:
    """Team section: tmux panes + inline preview + expand button.

    When ``panes`` contains ≥ ``_TOO_MANY_PANES_THRESHOLD`` entries the
    preview is suppressed (``preview_lines=None``) to control subprocess cost.
    ``capture_pane()`` is the v1 implementation and is not called in that case.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
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

    blocks: List[str] = []
    for window_name in order:
        row_parts = [
            _render_pane_row(
                pane,
                preview_lines=(
                    None if too_many
                    else _pane_last_n_lines(_pane_attr(pane, "pane_id", ""))
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


def _section_subagents(signals, heading: str = "Subagents (agent-pool)") -> str:
    """Subagent section: agent-pool signal slots grouped by scope.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
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
# ---------------------------------------------------------------------------
# TSK-01-04: Live Activity + Phase Timeline render functions
# ---------------------------------------------------------------------------

_KNOWN_PHASES = {"dd", "im", "ts", "xx"}
_LIVE_ACTIVITY_LIMIT = 20
_TIMELINE_MAX_ROWS = 50
_TIMELINE_SPAN_MINUTES = 60


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


def _fmt_hms(dt):
    """UTC-aware datetime을 HH:MM:SS 문자열로 변환한다."""
    return dt.astimezone(timezone.utc).strftime("%H:%M:%S")


def _fmt_elapsed_short(seconds):
    """경과 시간(초)을 짧은 문자열로 변환한다.

    None/음수 -> '-', 60 미만 -> '{n}s', 3600 미만 -> '{m}m {s}s', 그 이상 -> '{h}h {m}m'.
    """
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


def _live_activity_rows(tasks, features, limit=_LIVE_ACTIVITY_LIMIT):
    """tasks + features의 phase_history_tail을 평탄화하여 내림차순 상위 limit개를 반환한다.

    반환 원소: (item_id: str, entry: PhaseEntry, dt: datetime)
    entry.at 파싱 실패 시 skip (예외 없음).
    """
    collected = []
    for item in list(tasks or []) + list(features or []):
        item_id = getattr(item, "id", None) or ""
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            dt = _parse_iso_utc(getattr(entry, "at", None))
            if dt is None:
                continue
            collected.append((item_id, entry, dt))

    collected.sort(key=lambda t: t[2], reverse=True)
    return collected[:limit]


def _section_live_activity(model, heading: str = "Live Activity"):
    """Live Activity 섹션을 렌더링한다.

    모든 WBS 태스크 + 피처의 phase_history_tail을 평탄화하여 최신 20건을
    내림차순으로 activity-row div 목록으로 렌더한다.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []
    rows = _live_activity_rows(tasks, features)

    if not rows:
        return _empty_section("activity", heading, "no recent events")

    row_htmls = []
    for item_id, entry, dt in rows:
        event = getattr(entry, "event", None)
        from_s = getattr(entry, "from_status", None)
        to_s = getattr(entry, "to_status", None)
        elapsed_s = getattr(entry, "elapsed_seconds", None)

        # Map to_status to a data-to value matching v3 CSS [data-to="..."] selectors.
        to_phase = _phase_of(to_s) if to_s else None
        if to_phase in ("dd", "im", "ts"):
            data_to = "running"
        elif to_phase == "xx":
            data_to = "done"
        elif event and event.endswith(".fail"):
            data_to = "failed"
        elif event == "bypass":
            data_to = "bypass"
        else:
            data_to = "pending"

        time_str = _fmt_hms(dt)
        elapsed_str = _fmt_elapsed_short(elapsed_s)
        event_label = _esc(event or "")
        # Strip the bracket decoration for the from→to labels so the reference
        # design's '.from/.to' spans stay compact ("running"/"done" not "[im]"/"[xx]").
        from_label = _esc(_phase_label(from_s) or "")
        to_label = _esc(_phase_label(to_s) or "")

        evt_detail = (
            f'{event_label} <span class="arrow">&#x2192;</span>'
            f'<span class="from">{from_label}</span>'
            f'<span class="arrow">&#x2192;</span>'
            f'<span class="to">{to_label}</span>'
        )
        row_html = (
            f'<div class="arow" data-to="{data_to}">\n'
            f'  <span class="t">{_esc(time_str)}</span>\n'
            f'  <span class="tid">{_esc(item_id)}</span>\n'
            f'  <span class="evt">{evt_detail}</span>\n'
            f'  <span class="el">{_esc(elapsed_str)}</span>\n'
            '</div>'
        )
        row_htmls.append(row_html)

    body = '<div class="panel"><div class="activity" aria-live="polite">\n' + "\n".join(row_htmls) + '\n</div></div>'
    return _section_wrap("activity", heading, body)


def _phase_label(status_str):
    """Map '[dd]'/'[im]'/'[ts]'/'[xx]' to human-readable phase labels."""
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


def _timeline_rows(tasks, features, now, span_minutes=_TIMELINE_SPAN_MINUTES):
    """tasks + features를 phase segment 행 리스트로 변환한다.

    phase_history_tail이 0건인 item은 skip한다.
    반환 행: {'id', 'title', 'bypassed', 'segments': [(start_dt, end_dt, phase, fail), ...]}
    """
    result = []
    for item in list(tasks or []) + list(features or []):
        item_id = getattr(item, "id", None) or ""
        title = getattr(item, "title", None)
        bypassed = bool(getattr(item, "bypassed", False))
        tail = getattr(item, "phase_history_tail", None) or []

        if not tail:
            continue

        pairs = []
        for e in tail:
            dt = _parse_iso_utc(getattr(e, "at", None))
            if dt is None:
                continue
            pairs.append((e, dt))

        pairs.sort(key=lambda p: p[1])

        segments = []
        for i, (e, dt) in enumerate(pairs):
            phase = _phase_of(getattr(e, "to_status", None))
            if phase is None:
                continue
            end_dt = pairs[i + 1][1] if i + 1 < len(pairs) else now
            event = getattr(e, "event", None)
            fail = bool(event and event.endswith(".fail"))
            segments.append((dt, end_dt, phase, fail))

        if not segments:
            continue

        result.append({
            "id": item_id,
            "title": title,
            "bypassed": bypassed,
            "segments": segments,
        })

    return result


def _x_of(t, now, span_minutes, W=600):
    """t 시각을 SVG X 좌표로 변환한다 (0.0 ~ W 클램프)."""
    origin = now - timedelta(minutes=span_minutes)
    delta_sec = (t - origin).total_seconds()
    total_sec = span_minutes * 60
    return max(0.0, min(float(W), W * delta_sec / total_sec))


def _timeline_svg(rows, span_minutes, now, max_rows=_TIMELINE_MAX_ROWS, W=600):
    """SVG 타임라인을 생성한다.

    빈 rows이면 empty-state SVG를 반환한다. max_rows 초과 row는 잘린다.
    외부 자원 참조 없음, 시간 파싱 실패 이벤트 skip.
    """
    if not rows:
        return (
            '<svg class="timeline-svg" viewBox="0 0 ' + str(W) + ' 40">\n'
            '  <text x="' + str(W // 2) + '" y="24" text-anchor="middle" '
            'fill="var(--muted)">no phase history</text>\n'
            '</svg>'
        )

    visible = rows[:max_rows]
    row_count = len(visible)
    H = row_count * 20

    parts = []
    parts.append(
        '<svg class="timeline-svg" viewBox="0 0 ' + str(W) + ' ' + str(H) + '">'
    )

    # <defs> — 해칭 패턴
    parts.append(
        '  <defs>\n'
        '    <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse"'
        ' patternTransform="rotate(45)">\n'
        '      <line x1="0" y1="0" x2="0" y2="6" stroke="var(--red)" stroke-width="2"/>\n'
        '    </pattern>\n'
        '  </defs>'
    )

    # X축 tick (13개: i=0..12, 5분 간격)
    tick_parts = ['  <g class="tl-ticks">']
    for i in range(13):
        x = i * W / 12
        minutes_ago = span_minutes - i * (span_minutes / 12)
        label = "0m" if i == 12 else ("-" + str(int(minutes_ago)) + "m")
        tick_parts.append(
            '    <line x1="' + ("%.1f" % x) + '" y1="0" x2="' + ("%.1f" % x) + '" y2="' + str(H) + '" '
            'stroke="var(--border)" stroke-width="0.5"/>'
        )
        tick_parts.append(
            '    <text x="' + ("%.1f" % x) + '" y="' + str(H - 4) + '" text-anchor="middle" '
            'font-size="8" fill="var(--muted)">' + _esc(label) + '</text>'
        )
    tick_parts.append('  </g>')
    parts.extend(tick_parts)

    # 각 row 렌더
    for row_idx, row in enumerate(visible):
        y_base = row_idx * 20
        bypassed = row.get("bypassed", False)
        segments = row.get("segments", [])

        g_parts = ['  <g transform="translate(0,' + str(y_base) + ')">']

        for start_dt, end_dt, phase, fail in segments:
            x1 = _x_of(start_dt, now, span_minutes, W)
            x2 = _x_of(end_dt, now, span_minutes, W)
            rect_w = max(1.0, x2 - x1)

            g_parts.append(
                '    <rect x="' + ("%.1f" % x1) + '" y="2" width="' + ("%.1f" % rect_w) + '" height="16" '
                'class="tl-' + _esc(phase) + '"/>'
            )

            if fail:
                g_parts.append(
                    '    <rect x="' + ("%.1f" % x1) + '" y="2" width="' + ("%.1f" % rect_w) + '" height="16" '
                    'class="tl-fail"/>'
                )

        if bypassed:
            g_parts.append(
                '    <text x="' + str(W + 5) + '" y="13" font-size="10">\U0001f7e1</text>'
            )

        g_parts.append('  </g>')
        parts.extend(g_parts)

    parts.append('</svg>')
    return "\n".join(parts)


def _section_phase_timeline(tasks, features, heading: str = "Phase Timeline"):
    """Phase Timeline 섹션을 렌더링한다 (v3: CSS positional .tl-track/.seg divs).

    시간축: 현재 - 60분 = left:0%, 현재 = left:100%.
    Task 수 50 초과 시 상위 50건만 렌더 후 +N more 링크 표시.
    SVG 사용 안 함 — CSS left%/width% 배치.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    """
    now = datetime.now(timezone.utc)
    rows = _timeline_rows(tasks, features, now)

    total = len(rows)
    visible = rows[:_TIMELINE_MAX_ROWS]

    if not visible:
        body = '<p class="tl-empty">no phase history</p>'
        return _section_wrap("timeline", heading, body)

    span_sec = _TIMELINE_SPAN_MINUTES * 60
    origin = now - timedelta(minutes=_TIMELINE_SPAN_MINUTES)

    def _left_pct(t):
        delta = (t - origin).total_seconds()
        return max(0.0, min(100.0, delta / span_sec * 100))

    def _width_pct(start_t, end_t):
        l = _left_pct(start_t)
        r = _left_pct(end_t)
        return max(0.1, r - l)

    # v3 segment class mapping: phase + fail → semantic colour
    # (matches .tl-track .seg-done/.seg-running/.seg-failed/.seg-bypass in CSS)
    _PHASE_TO_SEG = {"dd": "running", "im": "running", "ts": "running", "xx": "done"}

    track_rows = []
    for row in visible:
        item_id = _esc(row.get("id", ""))
        bypassed = row.get("bypassed", False)
        segs = row.get("segments", [])
        seg_divs = []
        total_segs = len(segs)
        for i, (start_dt, end_dt, phase, fail) in enumerate(segs):
            l = _left_pct(start_dt)
            w = _width_pct(start_dt, end_dt)
            if fail:
                cls = "failed"
            elif bypassed and i == total_segs - 1:
                cls = "bypass"
            else:
                cls = _PHASE_TO_SEG.get(phase, "running")
            seg_divs.append(
                f'<div class="seg seg-{cls}"'
                f' style="left:{l:.2f}%;width:{w:.2f}%"></div>'
            )
        segs_html = "\n    ".join(seg_divs) if seg_divs else ""
        track_rows.append(
            f'<div class="tl-row" data-id="{item_id}">\n'
            f'  <span class="lbl">{item_id}</span>\n'
            f'  <div class="tl-track">\n'
            f'    {segs_html}\n'
            f'  </div>\n'
            f'</div>'
        )

    # X-axis labels (tl-axis) — 5 major ticks at 0/25/50/75/100%
    axis_ticks = []
    for i in range(5):
        pct = i * 25
        mins_ago = _TIMELINE_SPAN_MINUTES - i * (_TIMELINE_SPAN_MINUTES // 4)
        label = "now" if mins_ago == 0 else f"−{mins_ago}m"
        axis_ticks.append(
            f'<div class="tick major" style="left:{pct}%"></div>'
            f'<div class="tlabel" style="left:{pct}%">{_esc(label)}</div>'
        )

    # Current-time indicator at right edge
    tl_now_html = '<div class="tl-now" style="left:100%"></div>'

    more_html = ""
    if total > _TIMELINE_MAX_ROWS:
        extra = total - _TIMELINE_MAX_ROWS
        more_html = (
            f'\n<p class="timeline-more">'
            f'<a href="#timeline-full">+{extra} more</a></p>'
        )

    header_html = (
        '<div class="timeline-head">\n'
        f'  <span>−{_TIMELINE_SPAN_MINUTES}m</span>\n'
        '  <span>now</span>\n'
        '</div>'
    )

    axis_row_html = (
        '<div class="tl-row" style="margin-top:8px;">\n'
        '  <span class="lbl"></span>\n'
        '  <div class="tl-axis" aria-hidden="true">\n'
        + "\n".join(axis_ticks)
        + f'\n    {tl_now_html}\n'
        + '  </div>\n'
        '</div>'
    )

    body = (
        '<div class="panel timeline">\n'
        + header_html + '\n'
        + "\n".join(track_rows)
        + '\n'
        + axis_row_html
        + '\n</div>'
        + more_html
    )
    return _section_wrap("timeline", heading, body)

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
    drawerPaneId:null,drawerPollId:null,clockId:null
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
  /* ---- dashboard polling (TSK-02-01) ---- */
  function stopMainPoll(){
    if(state.mainPollId!==null){clearInterval(state.mainPollId);state.mainPollId=null;}
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){} state.mainAbort=null;}
  }
  function startMainPoll(){
    stopMainPoll();
    tick();
    state.mainPollId=setInterval(tick,5000);
  }
  function tick(){
    if(!state.autoRefresh)return;
    if(state.mainAbort){try{state.mainAbort.abort();}catch(e){}}
    state.mainAbort=new AbortController();
    fetchAndPatch(state.mainAbort.signal);
  }
  function fetchAndPatch(signal){
    fetch(window.location.search?'/'+window.location.search:'/',{cache:'no-store',signal:signal})
      .then(function(r){return r.ok?r.text():null;})
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
        if(first){first.focus();}
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
    pre.textContent=(j.lines||[]).join('\\n');
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
    startMainPoll();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init);
  }else{
    init();
  }
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
        '  <pre class="drawer-pre" data-drawer-pre tabindex="0"></pre>\n'
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
# TSK-01-02: Subproject tabs nav section
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


def _build_dashboard_body(s: dict) -> str:
    """Assemble section HTMLs into the ``<body>`` inner content string (v3 layout).

    v3 layout mirrors the reference ``dev-plugin Monitor.html``:
      shell > cmdbar → kpi → grid[ col-left: wp-cards + features,
                                    col-right: activity + timeline + team + subagents ]
             → phase-history

    The entire page is wrapped in ``<div class="shell">`` so the cmdbar's
    sticky/backdrop effect aligns with the KPI strip and grid columns.
    """
    wbs_landing_pad = '<a id="wbs" aria-hidden="true" tabindex="-1"></a>\n'
    # TSK-01-02: subproject-tabs is optional (empty string in legacy mode)
    tabs_html = s.get("subproject-tabs", "")

    return "".join([
        '<div class="shell">\n',
        s["header"], "\n",
        tabs_html,
        s["kpi"], "\n",
        '  <div class="grid">\n',
        '    <div class="col">\n',
        wbs_landing_pad,
        s["wp-cards"], "\n",
        s["features"], "\n",
        '    </div>\n',
        '    <div class="col">\n',
        s["live-activity"], "\n",
        s["phase-timeline"], "\n",
        s["team"], "\n",
        s["subagents"], "\n",
        '    </div>\n',
        '  </div>\n',
        s["phase-history"], "\n",
        '</div>\n',
    ])


def render_dashboard(model: dict, lang: str = "ko", subproject: str = "") -> str:
    """Render the full v2 monitor dashboard HTML document (TSK-01-06).

    Assembly order (design.md §구현방향):
      sticky_header → kpi → .page[col-left: wp_cards + features,
      col-right: live_activity + phase_timeline + team + subagents]
      → phase_history (full-width footer)

    Changes from v1:
    - ``<meta http-equiv="refresh">`` removed (JS polling TBD in WP-02).
    - ``.page`` 2-column grid wrapper added.
    - ``data-section="{key}"`` injected on each section for JS partial updates.
    - ``_drawer_skeleton()`` injected before ``</body>``.
    - Empty ``<script id="dashboard-js">`` placeholder inserted for WP-02.
    - ``<a id="wbs">`` landing pad added before wp-cards for backward compat.

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

    # Build each section HTML.  ``header`` is excluded from data-section
    # injection (it is nav metadata, not a JS partial-update target).
    # TSK-01-02: subproject-tabs is also excluded from wrap (it has its own
    # data-section already via _section_subproject_tabs).
    header_html = _section_header(model, lang=lang, subproject=subproject)
    tabs_html = _section_subproject_tabs(model)
    sections: dict = {
        "kpi":            _section_kpi(model),
        "wp-cards":       _section_wp_cards(tasks, running_ids, failed_ids,
                                            heading=_t(lang, "work_packages")),
        "features":       _section_features(features, running_ids, failed_ids,
                                            heading=_t(lang, "features")),
        "live-activity":  _section_live_activity(model,
                                                  heading=_t(lang, "live_activity")),
        "phase-timeline": _section_phase_timeline(tasks, features,
                                                   heading=_t(lang, "phase_timeline")),
        "team":           _section_team(panes, heading=_t(lang, "team_agents")),
        "subagents":      _section_subagents(ap_sigs,
                                              heading=_t(lang, "subagents")),
        "phase-history":  _section_phase_history(tasks, features),
    }

    # Inject data-section attribute on each section's outermost tag.
    for key, html in sections.items():
        sections[key] = _wrap_with_data_section(html, key)

    body = _build_dashboard_body({**sections, "header": header_html, "subproject-tabs": tabs_html})

    return "".join([
        '<!DOCTYPE html>\n',
        '<html lang="en">\n',
        '<head>\n',
        '  <meta charset="utf-8">\n',
        '  <title>dev-plugin Monitor</title>\n',
        f'  <style>{DASHBOARD_CSS}</style>\n',
        '</head>\n',
        '<body>\n',
        body, "\n",
        _drawer_skeleton(), "\n",
        f'<script id="dashboard-js">{_DASHBOARD_JS}</script>\n',
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
        if scope == project_name or scope.startswith(prefix):
            result.append(sig)
    return result


# ---------------------------------------------------------------------------
# TSK-01-01: /api/state 쿼리 파라미터 헬퍼 (순수 함수 — 테스트 용이)
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

    # TSK-01-01 / TSK-01-02: discover subprojects from original docs_dir root
    # (docs_dir may already be narrowed to subproject; use project_root to
    # find the original docs root — but for discover we need the top-level
    # docs dir, which is stored in the server's docs_dir attribute).
    available_subprojects = discover_subprojects(docs_dir)
    is_multi_mode = bool(available_subprojects)
    project_name = os.path.basename(os.path.normpath(project_root)) if project_root else ""

    return {
        "generated_at": _now_iso_z(),
        "project_root": project_root or "",
        "docs_dir": docs_dir or "",
        "wbs_tasks": tasks,
        "features": features,
        "shared_signals": shared_signals,
        "agent_pool_signals": agent_pool_signals,
        "tmux_panes": panes,
        # TSK-01-02: new fields
        "project_name": project_name,
        "subproject": subproject,
        "available_subprojects": available_subprojects,
        "is_multi_mode": is_multi_mode,
        "lang": lang,
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

    TSK-01-01 extension: parses ``?subproject=``, ``?lang=``,
    ``?include_pool=``, ``?refresh=`` query parameters and injects 7 new
    top-level fields (``subproject``, ``available_subprojects``,
    ``is_multi_mode``, ``project_name``, ``generated_at`` (pre-existing),
    ``project_root`` (pre-existing), ``docs_dir`` (pre-existing)) into the
    response.  Existing 8 keys are preserved unchanged for legacy
    compatibility.

    All scanner exceptions are caught and mapped to a 500 JSON envelope; one
    line is logged to stderr so the server operator can see the failure.
    """
    try:
        # --- 1. Query parameter parsing (TSK-01-01) ---
        raw_path = getattr(handler, "path", "") or ""
        _qs = urlsplit(raw_path).query
        qp = _parse_state_query_params(_qs)
        subproject: str = qp["subproject"]
        include_pool: bool = qp["include_pool"]

        project_root: str = _server_attr(handler, "project_root")
        docs_dir: str = _server_attr(handler, "docs_dir")

        # --- 2. Subproject discovery ---
        available_subprojects: List[str] = discover_subprojects(docs_dir)
        is_multi_mode: bool = bool(available_subprojects)

        # --- 3. effective_docs_dir for scan_tasks / scan_features ---
        effective_docs_dir: str = _resolve_effective_docs_dir(docs_dir, subproject)

        # --- 4. Build base snapshot using effective_docs_dir ---
        payload = _build_state_snapshot(
            project_root=project_root,
            docs_dir=effective_docs_dir,
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )

        # --- 5. Post-processing pipeline ---
        # 5a. Subproject filter on shared_signals / tmux_panes
        payload = _apply_subproject_filter(payload, subproject)

        # 5b. agent_pool_signals exclusion when include_pool=0 (default)
        payload = _apply_include_pool(payload, include_pool)

        # --- 6. Inject 7 new top-level fields (TSK-01-01 schema extension) ---
        project_name: str = (
            getattr(getattr(handler, "server", None), "project_name", None)
            or os.path.basename(project_root)
            or ""
        )
        payload = {
            **payload,
            "subproject": subproject,
            "available_subprojects": available_subprojects,
            "is_multi_mode": is_multi_mode,
            "project_name": project_name,
        }
        # generated_at / project_root / docs_dir are already in payload
        # (from _build_state_snapshot), so they satisfy the "7 fields" count.

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
            pane_id = _extract_pane_id(path, _API_PANE_PATH_PREFIX)
            _handle_pane_api(self, pane_id)
        elif _is_pane_html_path(path):
            pane_id = _extract_pane_id(path, _PANE_PATH_PREFIX)
            _handle_pane_html(self, pane_id)
        else:
            self._route_not_found()

    # ------------------------------------------------------------------
    # Route implementations
    # ------------------------------------------------------------------

    def _route_root(self) -> None:
        """GET / — parse query, build model dict and render dashboard HTML.

        TSK-01-02: Parses ``?subproject=`` and ``?lang=`` query parameters,
        discovers subprojects, resolves effective_docs_dir, and composes
        filter closures before calling :func:`_build_render_state`.

        Uses :func:`_build_render_state` (raw dataclass lists) instead of
        :func:`_build_state_snapshot` (dict lists) because the renderer
        accesses fields via ``getattr(item, "id")``; dict items would silently
        render as empty spans.

        TSK-02-02: Parses ?lang= and ?subproject= query parameters.
        """
        from urllib.parse import parse_qs

        server = getattr(self, "server", None)
        refresh_seconds = int(getattr(server, "refresh_seconds", _DEFAULT_REFRESH_SECONDS))

        no_tmux = bool(getattr(server, "no_tmux", False))
        _tmux_fn = (lambda: None) if no_tmux else list_tmux_panes

        project_root = _server_attr(self, "project_root")
        base_docs_dir = _server_attr(self, "docs_dir")

        # --- TSK-01-02: query parsing ---
        query_string = urlsplit(self.path).query or ""
        qs = parse_qs(query_string, keep_blank_values=False)
        raw_sp = (qs.get("subproject") or ["all"])[0] or "all"
        lang = (qs.get("lang") or ["ko"])[0] or "ko"

        # Discover available subprojects from base docs dir
        available_subprojects = discover_subprojects(base_docs_dir)
        is_multi_mode = bool(available_subprojects)

        # Validate subproject whitelist (path-traversal guard + fallback)
        if raw_sp != "all" and raw_sp not in available_subprojects:
            sys.stderr.write(
                f"[monitor] unknown subproject={raw_sp!r}, falling back to 'all'\n"
            )
            raw_sp = "all"
        subproject = raw_sp

        # Resolve effective docs dir
        effective_docs_dir = _resolve_effective_docs_dir(base_docs_dir, subproject)

        # Build project_name for filter helpers
        project_name: str = (
            getattr(server, "project_name", None)
            or os.path.basename(os.path.normpath(project_root))
            or ""
        )

        # Compose filter closures (layer 1: project, layer 2: subproject)
        def _scan_signals_f() -> List[SignalEntry]:
            raw_sigs = scan_signals()
            if project_name:
                raw_sigs = _filter_signals_by_project(raw_sigs, project_name)
            if subproject != "all" and project_name:
                filtered = _filter_by_subproject(raw_sigs, subproject, project_name)
                raw_sigs = filtered["signals"]
            return raw_sigs

        def _list_panes_f() -> Optional[List[PaneInfo]]:
            raw_panes = _tmux_fn()
            if raw_panes is None:
                return None
            if project_root and project_name:
                raw_panes = _filter_panes_by_project(raw_panes, project_root, project_name)
            if subproject != "all" and project_name:
                filtered = _filter_by_subproject(raw_panes, subproject, project_name)
                raw_panes = filtered["panes"]
            return raw_panes

        state = _build_render_state(
            project_root=project_root,
            docs_dir=effective_docs_dir,
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=_scan_signals_f,
            list_tmux_panes=_list_panes_f,
            subproject=subproject,
            lang=lang,
        )
        # Override available_subprojects and is_multi_mode from top-level docs dir
        # (_build_render_state computes them from effective_docs_dir which may be a subdir)
        state["available_subprojects"] = available_subprojects
        state["is_multi_mode"] = is_multi_mode
        model = {**state, "refresh_seconds": refresh_seconds}

        # Parse ?lang= and ?subproject= query parameters (TSK-02-02).
        query_string = urlsplit(self.path).query or ""
        query_params = parse_qs(query_string)

        lang = _normalize_lang((query_params.get("lang") or ["ko"])[0])

        subproject = (query_params.get("subproject") or [""])[0]

        html_body = render_dashboard(model, lang=lang, subproject=subproject)
        _send_html_response(self, 200, html_body)

    def _route_api_state(self) -> None:
        """GET /api/state — delegate to _handle_api_state."""
        server = getattr(self, "server", None)
        no_tmux = bool(getattr(server, "no_tmux", False))
        _tmux_fn = (lambda: None) if no_tmux else list_tmux_panes
        _handle_api_state(self, list_tmux_panes=_tmux_fn)

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
