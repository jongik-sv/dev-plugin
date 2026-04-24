"""monitor_server.signals — 시그널 파일 스캔 + WP busy 집계.

core.py 분해 (core-decomposition:C1-2) 결과 산출된 모듈.

포함 심볼:
- SignalEntry dataclass (TRD §5.2)
- _iso_mtime, _signal_entry, _walk_signal_entries
- scan_signals, scan_signals_cached
- _wp_busy_set (WP 레벨 busy 집계)
- 신호 스캔용 상수 (_SIGNAL_KINDS, _AGENT_POOL_*, _WP_*)

_SIGNALS_CACHE 는 caches 모듈에서 import한다. 캐시 인스턴스와 캐시 경유 함수
(scan_signals_cached)가 동일 모듈에 있어야 모듈 전역 이름 참조가 안전하다
(design.md §4.1 참고).
"""
from __future__ import annotations

import glob
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from monitor_server.caches import _SIGNALS_CACHE
except (ImportError, ModuleNotFoundError):
    # flat-load fallback: caches.py 를 'monitor_server.caches' 키로 등록.
    # core.py 의 _c1_bootstrap_submodules 와 동일한 키를 사용하여
    # core/signals 가 같은 caches 인스턴스를 공유하게 한다.
    import importlib.util as _sig_ilu  # type: ignore
    import sys as _sig_sys
    from pathlib import Path as _SigPath
    _sig_key = "monitor_server.caches"
    _sig_mod = _sig_sys.modules.get(_sig_key)
    if _sig_mod is None:
        _sig_caches_path = _SigPath(__file__).resolve().parent / "caches.py"
        _sig_spec = _sig_ilu.spec_from_file_location(_sig_key, str(_sig_caches_path))
        _sig_mod = _sig_ilu.module_from_spec(_sig_spec)
        _sig_sys.modules[_sig_key] = _sig_mod
        _sig_spec.loader.exec_module(_sig_mod)  # type: ignore[union-attr]
    _SIGNALS_CACHE = _sig_mod._SIGNALS_CACHE

__all__ = [
    "SignalEntry",
    "_iso_mtime",
    "_signal_entry",
    "_walk_signal_entries",
    "scan_signals",
    "scan_signals_cached",
    "_wp_busy_set",
    "_SIGNAL_KINDS",
    "_AGENT_POOL_DIR_PREFIX",
    "_AGENT_POOL_SCOPE_PREFIX",
    "_WP_SIGNAL_PREFIX_RE",
    "_WP_ID_RE",
]


_SIGNAL_KINDS = {"running", "done", "failed", "bypassed"}

# Agent-pool signal directory prefix and scope prefix (scan_signals + _classify_signal_scopes).
_AGENT_POOL_DIR_PREFIX = "agent-pool-signals-"
_AGENT_POOL_SCOPE_PREFIX = "agent-pool:"

# WP-scoped signal task_id prefix pattern (e.g. "WP-01-").
_WP_SIGNAL_PREFIX_RE = re.compile(r"^WP-\d{2}-")

# wp-progress-spinner: WP 레벨 busy 감지 패턴 (^WP-\d{2}$).
# _WP_SIGNAL_PREFIX_RE (^WP-\d{2}-)는 Task 레벨 신호 감지용이므로 별도 패턴 사용.
_WP_ID_RE = re.compile(r"^WP-\d{2}$")


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
    content: str = ""


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
    content = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read(500)
        first_line = raw.splitlines()[0].strip() if raw.strip() else ""
        content = first_line[:200]
    except OSError:
        pass
    return SignalEntry(
        name=name,
        kind=ext,
        task_id=stem,
        mtime=_iso_mtime(path),
        scope=scope,
        content=content,
    )


def _walk_signal_entries(root: str, scope: str) -> List[SignalEntry]:
    """Recursively collect valid ``SignalEntry`` items under *root* with *scope*.

    Returns ``[]`` if *root* is not an existing directory — callers do not need to
    pre-check ``os.path.isdir``. Files with unknown extensions are silently
    skipped by ``_signal_entry``.

    Subdirectories whose name starts with ``_`` are treated as archive/private
    (Jekyll/pytest convention) and pruned from the walk. This protects live
    signal state from being polluted by manual backups like ``_backup-{ts}/``
    left behind after WBS resume cleanup.
    """
    if not os.path.isdir(root):
        return []
    collected: List[SignalEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune archive/private subdirs in-place so os.walk skips their contents.
        dirnames[:] = [d for d in dirnames if not d.startswith("_")]
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


def scan_signals_cached() -> "List[SignalEntry]":
    """Return ``scan_signals()`` result from the 1-second TTL cache.

    Cache key: ``"signals"`` (singleton — all requests share the same cache slot).
    On a cache miss, calls ``scan_signals()``, stores the result, and returns it.
    The empty-list case ``[]`` is a valid cache value; it is not confused with a
    miss (the cache uses a ``(value, hit)`` tuple protocol).
    """
    value, hit = _SIGNALS_CACHE.get("signals")
    if hit:
        return value  # type: ignore[return-value]
    result = scan_signals()
    _SIGNALS_CACHE.set("signals", result)
    return result


def _wp_busy_set(signals: "List[SignalEntry]") -> "Dict[str, str]":
    """WP 레벨 busy 상태를 {wp_id: label} 딕셔너리로 반환한다.

    kind="running" AND task_id가 ^WP-\\d{2}$ 패턴인 시그널만 추출.
    content 첫 줄 키워드로 레이블 결정:
      - "merge" 포함 → "통합 중"
      - "test" 포함 → "테스트 중"
      - 그 외 → "처리 중"

    wp-progress-spinner feature: 기존 _WP_SIGNAL_PREFIX_RE(^WP-\\d{2}-)는
    Task 레벨 신호 감지용이므로 WP 레벨 감지에는 별도 _WP_ID_RE(^WP-\\d{2}$) 사용.
    """
    result: "Dict[str, str]" = {}
    for sig in signals:
        if sig.kind != "running":
            continue
        if not _WP_ID_RE.match(sig.task_id):
            continue
        content_lower = sig.content.lower()
        if "merge" in content_lower:
            label = "통합 중"
        elif "test" in content_lower:
            label = "테스트 중"
        else:
            label = "처리 중"
        result[sig.task_id] = label
    return result
