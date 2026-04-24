"""monitor_server.renderers.taskrow — Task row 렌더링 공용 헬퍼.

TSK-02-01: _phase_label, _phase_data_attr, _trow_data_status 공용 헬퍼 이전.
TSK-03-01: _phase_data_attr (단순 문자열 매핑 버전) 추가.

Note:
  monitor-server.py 의 _phase_data_attr(status_code, *, failed, bypassed) 와
  이름이 같지만 시그니처가 다르다.
  - monitor-server.py 버전: failed/bypassed boolean 플래그로 우선순위 분기
  - 본 모듈 버전: 단순 status_code 문자열 → data-phase 속성값 매핑 (pure function)
  downstream Task(TSK-03-03, TSK-04-01)가 이 시그니처를 테스트로 고정한다.
"""

from __future__ import annotations

# ── Phase label tables ─────────────────────────────────────────────────────

_PHASE_LABELS: dict[str, dict[str, str]] = {
    "[dd]":    {"ko": "Design",  "en": "Design"},
    "[im]":    {"ko": "Build",   "en": "Build"},
    "[ts]":    {"ko": "Test",    "en": "Test"},
    "[xx]":    {"ko": "Done",    "en": "Done"},
    "failed":  {"ko": "Failed",  "en": "Failed"},
    "bypass":  {"ko": "Bypass",  "en": "Bypass"},
    "pending": {"ko": "Pending", "en": "Pending"},
}


def _phase_label(status_code: str | None, lang: str = "ko") -> str:
    """Return human-readable badge label for a Task row.

    Simplified version for taskrow renderer — no failed/bypassed flags.
    Use monitor-server._phase_label for the full priority-chain version.
    """
    code = str(status_code).strip() if status_code else ""
    entry = _PHASE_LABELS.get(code)
    if entry:
        normalised = lang if lang in entry else "ko"
        return entry[normalised]
    return _PHASE_LABELS["pending"].get(lang, _PHASE_LABELS["pending"]["ko"])


# ── Phase data-phase attribute mapping (TSK-03-01) ─────────────────────────

_PHASE_CODE_TO_ATTR: dict[str, str] = {
    "[dd]":   "dd",
    "[im]":   "im",
    "[ts]":   "ts",
    "[xx]":   "xx",
    "failed":  "failed",
    "bypass":  "bypass",
    "pending": "pending",
}


def _phase_data_attr(status_code: str) -> str:
    """Return data-phase attribute value for a given status code string.

    Pure function — no external state dependency.

    Input:  '[dd]' / '[im]' / '[ts]' / '[xx]' / 'failed' / 'bypass' / 'pending'
    Output: 'dd'   / 'im'  / 'ts'  / 'xx'  / 'failed' / 'bypass' / 'pending'
    Unknown input → 'pending'.

    Note: Distinct from monitor-server._phase_data_attr(status_code, *, failed, bypassed)
    which uses boolean priority flags. This function receives pre-resolved status
    strings only (downstream TSK-03-03, TSK-04-01 fix this signature via tests).
    """
    return _PHASE_CODE_TO_ATTR.get(str(status_code).strip(), "pending")
