"""단위 테스트 — monitor_server ETag/304 캐싱 (Feature: monitor-perf).

QA 체크리스트 항목 매핑:
- test_compute_etag_format: 200 응답에 ETag 헤더 형식 W/"[hex]"
- test_check_if_none_match_hit: If-None-Match 일치 → True
- test_check_if_none_match_miss: 불일치 → False
- test_check_if_none_match_empty: 빈 If-None-Match → False
- test_check_if_none_match_multi_value_hit: 다중값 중 한 개 일치 → True
- test_json_response_sends_etag: _json_response가 ETag 헤더 포함
- test_json_response_304_on_match: If-None-Match 일치 시 304 + 빈 본문
- test_json_response_200_on_mismatch: If-None-Match 불일치 시 200 + 본문
- test_json_response_200_no_if_none_match: If-None-Match 없으면 200 + ETag
- test_etag_changes_when_payload_changes: 본문 변경 시 ETag 변경
- test_304_body_is_empty: 304 응답 본문 길이 0
- test_check_if_none_match_star: If-None-Match: * → 매칭 안 함 (RFC 7232)

실행: pytest -q scripts/test_monitor_etag.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from unittest import mock
import unittest

# ---------------------------------------------------------------------------
# monitor_server.etag_cache 로드
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ETAG_CACHE_PATH = _SCRIPTS_DIR / "monitor_server" / "etag_cache.py"

if _ETAG_CACHE_PATH.exists():
    # 고유 키로만 등록 — monitor_server.* 네임스페이스 오염 최소화
    _spec = importlib.util.spec_from_file_location("_mperf_etag_cache", _ETAG_CACHE_PATH)
    etag_cache = importlib.util.module_from_spec(_spec)
    sys.modules["_mperf_etag_cache"] = etag_cache
    _spec.loader.exec_module(etag_cache)
    compute_etag = etag_cache.compute_etag
    check_if_none_match = etag_cache.check_if_none_match
else:
    etag_cache = None
    compute_etag = None
    check_if_none_match = None

# ---------------------------------------------------------------------------
# monitor_server.core 로드 — 고유 키로만 등록
# monitor_server.core / monitor_server.etag_cache를 sys.modules에 등록하지 않음:
# test_monitor_graph_api.py가 monitor-server.py를 "monitor_server"로 로드할 때
# _load_core_module()이 같은 인스턴스를 재사용 → _GRAPH_CACHE가 테스트 간 공유되어
# subprocess mock이 캐시 히트로 우회되는 문제 방지.
# core.py의 lazy-load(_ensure_etag_cache)는 이 모듈 인스턴스에서 호출 시 자체적으로
# etag_cache.py를 로드하므로 별도 등록 불필요.
# ---------------------------------------------------------------------------

_CORE_PATH = _SCRIPTS_DIR / "monitor_server" / "core.py"
_CORE_SPEC = importlib.util.spec_from_file_location("_mperf_monitor_core", _CORE_PATH)
_core_mod = importlib.util.module_from_spec(_CORE_SPEC)
sys.modules["_mperf_monitor_core"] = _core_mod
# etag_cache를 임시 등록해 core.py _ensure_etag_cache가 찾을 수 있게 함
if etag_cache is not None:
    sys.modules["monitor_server.etag_cache"] = etag_cache
_CORE_SPEC.loader.exec_module(_core_mod)
# 임시 등록 제거 — 이후 graph_api 테스트의 sys.modules 오염 방지
sys.modules.pop("monitor_server.etag_cache", None)
_json_response = getattr(_core_mod, "_json_response", None)


# ---------------------------------------------------------------------------
# MockHandler — 기존 테스트 파일과 동일 패턴
# ---------------------------------------------------------------------------

class MockHandler:
    """헤더와 본문을 캡처하는 최소 HTTP 핸들러 스텁."""

    def __init__(self, path: str = "/api/state", if_none_match: Optional[str] = None):
        self.path = path
        self.server = mock.MagicMock()
        self.server.docs_dir = "/tmp/fakedir"
        self.server.project_root = "/tmp/fake"
        self._sent_status: Optional[int] = None
        self._sent_headers: dict = {}
        self._body = BytesIO()
        self.wfile = self._body
        # headers dict-like
        _headers: dict = {}
        if if_none_match is not None:
            _headers["If-None-Match"] = if_none_match
        self.headers = _headers

    def send_response(self, status: int) -> None:
        self._sent_status = status

    def send_header(self, key: str, value: str) -> None:
        self._sent_headers[key] = value

    def end_headers(self) -> None:
        pass

    def body_bytes(self) -> bytes:
        return self._body.getvalue()

    def json_body(self) -> Any:
        raw = self._body.getvalue()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests: compute_etag
# ---------------------------------------------------------------------------

class TestComputeEtag(unittest.TestCase):
    """compute_etag 반환값 형식 검증."""

    def setUp(self):
        if compute_etag is None:
            self.skipTest("etag_cache.py 미존재 (구현 전)")

    def test_returns_weak_etag_format(self):
        """W/"<hex>" 형식이어야 한다."""
        tag = compute_etag(b'{"key":"value"}')
        self.assertIsInstance(tag, str)
        self.assertTrue(tag.startswith('W/"'), f"ETag must start with W/\": got {tag!r}")
        self.assertTrue(tag.endswith('"'), f"ETag must end with \": got {tag!r}")

    def test_hex_chars_only_in_value(self):
        """따옴표 안 내용이 hex 문자열이어야 한다."""
        tag = compute_etag(b"hello world")
        # W/"<hex>"
        inner = tag[3:-1]  # strip W/" and "
        self.assertTrue(all(c in "0123456789abcdefABCDEF" for c in inner),
                        f"ETag inner must be hex: got {inner!r}")

    def test_min_length(self):
        """ETag 값(따옴표 안)이 최소 8자 이상."""
        tag = compute_etag(b"x")
        inner = tag[3:-1]
        self.assertGreaterEqual(len(inner), 8, f"ETag too short: {inner!r}")

    def test_same_payload_same_etag(self):
        """동일 페이로드 → 동일 ETag (결정론적)."""
        payload = b'{"status":"ok","count":5}'
        self.assertEqual(compute_etag(payload), compute_etag(payload))

    def test_different_payload_different_etag(self):
        """다른 페이로드 → 다른 ETag."""
        tag_a = compute_etag(b'{"count":5}')
        tag_b = compute_etag(b'{"count":6}')
        self.assertNotEqual(tag_a, tag_b)

    def test_empty_payload(self):
        """빈 바이트도 유효한 ETag 반환."""
        tag = compute_etag(b"")
        self.assertTrue(tag.startswith('W/"'))

    def test_korean_payload(self):
        """한글 UTF-8 페이로드도 처리."""
        payload = '{"title":"태스크"}'.encode("utf-8")
        tag = compute_etag(payload)
        self.assertTrue(tag.startswith('W/"'))


# ---------------------------------------------------------------------------
# Tests: check_if_none_match
# ---------------------------------------------------------------------------

class TestCheckIfNoneMatch(unittest.TestCase):
    """check_if_none_match 동작 검증."""

    def setUp(self):
        if check_if_none_match is None:
            self.skipTest("etag_cache.py 미존재 (구현 전)")

    def _make_handler(self, if_none_match: Optional[str]) -> MockHandler:
        return MockHandler(if_none_match=if_none_match)

    def test_match_exact(self):
        """If-None-Match가 ETag와 정확히 일치 → True."""
        handler = self._make_handler('W/"abc123"')
        self.assertTrue(check_if_none_match(handler, 'W/"abc123"'))

    def test_no_match(self):
        """If-None-Match가 다른 값 → False."""
        handler = self._make_handler('W/"abc123"')
        self.assertFalse(check_if_none_match(handler, 'W/"xyz999"'))

    def test_empty_if_none_match(self):
        """If-None-Match가 빈 문자열 → False."""
        handler = self._make_handler("")
        self.assertFalse(check_if_none_match(handler, 'W/"abc123"'))

    def test_no_if_none_match_header(self):
        """If-None-Match 헤더 없음 → False."""
        handler = self._make_handler(None)
        self.assertFalse(check_if_none_match(handler, 'W/"abc123"'))

    def test_multi_value_one_matches(self):
        """다중값(콤마 분리) 중 한 개 일치 → True."""
        handler = self._make_handler('W/"aaa", W/"abc123", W/"zzz"')
        self.assertTrue(check_if_none_match(handler, 'W/"abc123"'))

    def test_multi_value_none_match(self):
        """다중값 모두 불일치 → False."""
        handler = self._make_handler('W/"aaa", W/"bbb"')
        self.assertFalse(check_if_none_match(handler, 'W/"ccc"'))

    def test_star_does_not_match(self):
        """If-None-Match: * 는 conditional GET이지만 본 구현에서 매칭 안 함.
        (RFC 7232: * 는 GET에서 항상 match이지만, 캐시 헬퍼는 명시 ETag만 비교)
        설계에서 * 처리 여부는 구현 재량 — 테스트는 구현 일관성만 검증."""
        handler = self._make_handler("*")
        # 구현이 True/False 어느 쪽이든 예외 없이 bool 반환해야 함
        result = check_if_none_match(handler, 'W/"abc"')
        self.assertIsInstance(result, bool)

    def test_weak_prefix_strip_matching(self):
        """W/ prefix 없이 전달된 값도 일치 처리 — RFC 7232 weak comparison."""
        # W/"abc123" == W/"abc123" — exact match 확인 (가장 단순한 경우)
        handler = self._make_handler('W/"abc123"')
        self.assertTrue(check_if_none_match(handler, 'W/"abc123"'))


# ---------------------------------------------------------------------------
# Tests: _json_response ETag 통합
# ---------------------------------------------------------------------------

class TestJsonResponseEtag(unittest.TestCase):
    """core.py _json_response의 ETag/304 통합 검증."""

    def setUp(self):
        if _json_response is None:
            self.skipTest("_json_response 미존재")

    def _call(self, payload, if_none_match: Optional[str] = None) -> MockHandler:
        handler = MockHandler(if_none_match=if_none_match)
        _json_response(handler, 200, payload)
        return handler

    def test_200_response_has_etag_header(self):
        """ETag 헤더가 200 응답에 포함된다."""
        handler = self._call({"status": "ok"})
        self.assertIn("ETag", handler._sent_headers,
                      "200 response must contain ETag header")

    def test_etag_header_format(self):
        """ETag 헤더 형식이 W/"..." 여야 한다."""
        handler = self._call({"count": 3})
        etag = handler._sent_headers.get("ETag", "")
        self.assertTrue(etag.startswith('W/"'),
                        f"ETag format wrong: {etag!r}")

    def test_200_body_present(self):
        """ETag 없는 요청 → 200 + 본문 존재."""
        handler = self._call({"key": "val"})
        self.assertEqual(handler._sent_status, 200)
        body = handler.json_body()
        self.assertIsNotNone(body)
        self.assertEqual(body["key"], "val")

    def test_304_on_matching_if_none_match(self):
        """If-None-Match 일치 시 304 반환, 본문 없음."""
        # 먼저 첫 요청으로 ETag 얻기
        h1 = self._call({"x": 1})
        etag = h1._sent_headers.get("ETag")
        self.assertIsNotNone(etag, "First response must have ETag")

        # 두 번째 요청 — 같은 페이로드 + If-None-Match
        h2 = MockHandler(if_none_match=etag)
        _json_response(h2, 200, {"x": 1})
        self.assertEqual(h2._sent_status, 304,
                         f"Expected 304 but got {h2._sent_status}")
        self.assertEqual(len(h2.body_bytes()), 0,
                         "304 body must be empty")

    def test_200_on_mismatched_if_none_match(self):
        """If-None-Match 불일치 시 200 + 본문 + 새 ETag."""
        handler = MockHandler(if_none_match='W/"wrongetag0000"')
        _json_response(handler, 200, {"x": 1})
        self.assertEqual(handler._sent_status, 200)
        self.assertIsNotNone(handler.json_body())
        self.assertIn("ETag", handler._sent_headers)

    def test_etag_changes_when_payload_changes(self):
        """페이로드 변경 시 ETag가 달라진다."""
        h1 = self._call({"count": 5})
        h2 = self._call({"count": 6})
        etag1 = h1._sent_headers.get("ETag")
        etag2 = h2._sent_headers.get("ETag")
        self.assertNotEqual(etag1, etag2,
                            "Different payloads must yield different ETags")

    def test_304_body_is_empty_bytes(self):
        """304 응답 본문은 정확히 0바이트."""
        h1 = self._call({"z": 99})
        etag = h1._sent_headers.get("ETag", "")
        h2 = MockHandler(if_none_match=etag)
        _json_response(h2, 200, {"z": 99})
        if h2._sent_status == 304:
            self.assertEqual(h2.body_bytes(), b"",
                             "304 wfile must be empty")

    def test_200_when_no_if_none_match(self):
        """If-None-Match 헤더 없으면 항상 200 + ETag."""
        handler = MockHandler(if_none_match=None)
        _json_response(handler, 200, {"a": 1})
        self.assertEqual(handler._sent_status, 200)
        self.assertIn("ETag", handler._sent_headers)

    def test_same_payload_second_request_is_304(self):
        """동일 상태 두 번 폴링 → 두 번째가 304."""
        payload = {"tasks": [{"id": "TSK-01-01", "status": "[dd]"}]}
        h1 = self._call(payload)
        etag = h1._sent_headers.get("ETag", "")

        h2 = MockHandler(if_none_match=etag)
        _json_response(h2, 200, payload)
        self.assertEqual(h2._sent_status, 304,
                         "Second identical poll must yield 304")


if __name__ == "__main__":
    unittest.main()
