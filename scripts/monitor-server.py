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
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


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
# Entry point (skeleton — real CLI arrives with TSK-01-01)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover - skeleton placeholder
    # TSK-01-01 will replace this block with argparse + HTTPServer bootstrap.
    import sys

    sys.stderr.write(
        "monitor-server.py: HTTP bootstrap not yet wired (TSK-01-01 pending).\n"
    )
    sys.exit(0)
