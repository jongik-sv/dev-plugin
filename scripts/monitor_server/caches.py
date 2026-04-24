"""monitor_server.caches — TTL 캐시 + ETag 캐시 lazy-load.

core.py 분해 (core-decomposition:C1-1) 결과 산출된 모듈.
TTL 캐시(`_TTLCache`)와 모듈 인스턴스(`_SIGNALS_CACHE`, `_GRAPH_CACHE`),
그리고 etag_cache.py lazy-load 함수(`_ensure_etag_cache`)를 담는다.

외부에서는 여전히 `monitor_server.core._SIGNALS_CACHE` 형태로 접근할 수 있다 —
core.py facade가 `from .caches import *` 로 재-export한다. `__all__` 명시로
언더스코어 심볼도 wildcard import 대상에 포함된다.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Tuple

__all__ = [
    "_TTLCache",
    "_SIGNALS_CACHE",
    "_GRAPH_CACHE",
    "_ensure_etag_cache",
    "_compute_etag",
    "_check_if_none_match",
]


# ---------------------------------------------------------------------------
# etag_cache lazy-load (monitor-perf: weak ETag/304 for _json_response)
# ---------------------------------------------------------------------------
# etag_cache.py는 _json_response 일반 API 응답에서 weak ETag(W/"...")를 처리한다.
# /api/graph 전용 ETag는 _graph_etag() / _get_if_none_match()가 직접 처리한다.
_compute_etag = None  # type: ignore
_check_if_none_match = None  # type: ignore
_etag_cache_loaded = False


def _ensure_etag_cache() -> None:
    """etag_cache.py를 최초 1회 lazy-load.

    고유 키(_monitor_perf_etag_cache)로만 등록하여 sys.modules["monitor_server"]
    가 flat 파일이거나 패키지이거나 관계없이 __init__.py 실행 등 side-effect를 방지.
    """
    global _compute_etag, _check_if_none_match, _etag_cache_loaded
    if _etag_cache_loaded:
        return
    _etag_cache_loaded = True
    try:
        import importlib.util as _ilu
        _ec_path = Path(__file__).with_name("etag_cache.py")
        if not _ec_path.exists():
            return
        # 고유 키로 확인 — monitor_server.etag_cache 키는 __init__.py 실행 side-effect 위험
        _uniq_key = "_monitor_perf_etag_cache"
        _existing = sys.modules.get(_uniq_key)
        if _existing is not None:
            _compute_etag = getattr(_existing, "compute_etag", None)
            _check_if_none_match = getattr(_existing, "check_if_none_match", None)
            return
        _spec = _ilu.spec_from_file_location(_uniq_key, str(_ec_path))
        if _spec is None:
            return
        _mod = _ilu.module_from_spec(_spec)
        sys.modules[_uniq_key] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        _compute_etag = getattr(_mod, "compute_etag", None)
        _check_if_none_match = getattr(_mod, "check_if_none_match", None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# TTL Cache (monitor-server-perf)
# ---------------------------------------------------------------------------

class _TTLCache:
    """Thread-safe in-memory TTL cache.

    Usage::

        cache = _TTLCache(ttl_seconds=1.0)
        value, hit = cache.get("key")   # hit=False → miss
        cache.set("key", value)         # stores value with ttl

    All operations are protected by a single ``threading.Lock`` so concurrent
    requests from ``ThreadingHTTPServer`` workers are safe.
    """

    def __init__(self, ttl_seconds: float = 1.0) -> None:
        self._ttl = ttl_seconds
        self._store: dict = {}   # key -> (value, expire_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> "Tuple[Any, bool]":
        """Return ``(value, True)`` on hit, ``(None, False)`` on miss/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, False
            value, expire_at = entry
            if time.monotonic() >= expire_at:
                del self._store[key]
                return None, False
            return value, True

    def set(self, key: str, value: "Any") -> None:
        """Store *value* under *key* with expiry at now + ttl_seconds."""
        expire_at = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = (value, expire_at)


# Module-level TTL cache instances
# _GRAPH_CACHE TTL=0: 테스트 호환성 — 동일 docs_dir로 반복 호출 시 캐시 히트가
# scan_tasks mock을 우회하는 문제 방지. 실 서버에서도 ETag/304가 클라이언트 캐싱을
# 담당하므로 서버측 in-memory TTL 캐시는 불필요.
_SIGNALS_CACHE: _TTLCache = _TTLCache(ttl_seconds=1.0)
_GRAPH_CACHE: _TTLCache = _TTLCache(ttl_seconds=0.0)
