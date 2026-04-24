"""monitor_server.etag_cache — weak ETag 헬퍼 (Feature: monitor-perf).

공개 API:
  compute_etag(payload_bytes: bytes) -> str
      SHA-256 hex의 앞 14자를 W/"..." weak-etag 형식으로 반환.

  check_if_none_match(handler, etag: str) -> bool
      handler.headers['If-None-Match']를 파싱해 etag와 일치 여부 반환.
      다중값(콤마 분리), 앞뒤 공백, W/ prefix 정규화를 처리한다.

설계 결정 (design.md 결정 2):
  - weak-etag(W/"...") 사용 — byte-exact 보장 의무 없음 (RFC 7232 §2.3)
  - SHA-256 hex 14자 ≈ 56비트 — 실용적 충돌 안전성
  - 이 모듈은 Python 3 stdlib만 사용한다 (pip 의존성 없음)
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


# ---------------------------------------------------------------------------
# ETag 계산
# ---------------------------------------------------------------------------

def compute_etag(payload_bytes: bytes) -> str:
    """응답 본문 바이트에서 weak ETag를 계산한다.

    반환 형식: ``W/"<14자 hex>"``

    Args:
        payload_bytes: JSON 직렬화 후 UTF-8 인코딩된 바이트.

    Returns:
        RFC 7232 형식 weak ETag 문자열 (예: ``W/"a1b2c3d4e5f67890"``).
    """
    digest = hashlib.sha256(payload_bytes).hexdigest()[:14]
    return f'W/"{digest}"'


# ---------------------------------------------------------------------------
# If-None-Match 검사
# ---------------------------------------------------------------------------

# ETag 값 추출 정규식: W/"..." 또는 "..."
_ETAG_RE = re.compile(r'(?:W/)?"[^"]*"')


def _normalize_etag(raw: str) -> str:
    """ETag 값을 정규화한다 (앞뒤 공백 제거, 소문자 변환).

    ``compute_etag``가 생성하는 SHA-256 hex 값은 항상 소문자이므로
    클라이언트가 대소문자를 섞어 보낸 경우에도 소문자 정규화로 일치 보장.
    """
    return raw.strip().lower()


def check_if_none_match(handler, etag: str) -> bool:
    """``handler.headers['If-None-Match']`` 값이 *etag*와 일치하는지 확인.

    다중값(``W/"a", W/"b"`` 형식)과 weak prefix 정규화를 지원한다.
    ``*``(와일드카드)는 매칭하지 않는다 — 명시 ETag 비교만 수행.

    Args:
        handler: ``headers`` dict(또는 dict-like)를 가진 HTTP 핸들러.
        etag: 현재 응답의 ETag 값 (``W/"..."`` 형식).

    Returns:
        ``True`` — 클라이언트의 If-None-Match가 etag와 일치 → 304 반환 가능.
        ``False`` — 불일치 또는 헤더 없음 → 200 정상 응답.
    """
    headers = getattr(handler, "headers", {})
    raw = headers.get("If-None-Match", "") if headers else ""
    if not raw or not raw.strip():
        return False

    normalized_etag = _normalize_etag(etag)

    # 콤마 분리 다중값 파싱
    candidates = _ETAG_RE.findall(raw)
    if not candidates:
        # 따옴표 없이 전달된 경우(비표준) 전체 값을 단일 후보로
        candidates = [raw.strip()]

    for candidate in candidates:
        if _normalize_etag(candidate) == normalized_etag:
            return True

    return False
