"""
test_monitor_phase_tokens.py

TSK-03-01: Phase/Critical CSS 변수 토큰 + _phase_data_attr 헬퍼 검증.

test_root_variables_declared   — style.css에 8개 CSS 변수 모두 선언 확인
test_phase_data_attr_mapping   — _phase_data_attr 7가지 상태 매핑 단위 테스트
test_wcag_contrast_comments    — WCAG AA contrast 근거 주석 존재 확인

추가 edge-case (QA 체크리스트 §3):
  test_phase_data_attr_unknown_input — 미지정 입력 → "pending" 반환
  test_existing_variables_untouched  — 기존 CSS 변수 값 변경 없음 확인
"""

import importlib.util
import pathlib

_SCRIPTS_DIR = pathlib.Path(__file__).parent.resolve()

# style.css 경로
_STYLE_CSS = _SCRIPTS_DIR / "monitor_server" / "static" / "style.css"

# taskrow.py 경로
_TASKROW_PATH = _SCRIPTS_DIR / "monitor_server" / "renderers" / "taskrow.py"

# ────────────────────────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────────────────────────

def _css_text() -> str:
    assert _STYLE_CSS.exists(), f"style.css 파일이 없습니다: {_STYLE_CSS}"
    return _STYLE_CSS.read_text(encoding="utf-8")


def _load_taskrow_module():
    """renderers.taskrow 를 importlib 로 직접 로드하여 반환.

    다른 테스트가 sys.modules["monitor_server"] 에 monitor-server.py 를 등록한
    경우에도 영향 받지 않도록 파일 경로 기반 직접 로드를 사용한다.
    """
    assert _TASKROW_PATH.exists(), f"taskrow.py 파일이 없습니다: {_TASKROW_PATH}"
    spec = importlib.util.spec_from_file_location(
        "monitor_server_renderers_taskrow_isolated",
        _TASKROW_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# 모듈 수준에서 한 번만 로드 — 테스트마다 재로딩하지 않아도 됨
_TASKROW_MOD = _load_taskrow_module()

# 모듈 수준에서 함수 참조를 직접 바인딩 — 간접 호출 레이어 제거
_phase_data_attr = _TASKROW_MOD._phase_data_attr


# ────────────────────────────────────────────────────────────────
# tests
# ────────────────────────────────────────────────────────────────

def test_root_variables_declared():
    """style.css :root 블록에 8개 CSS 변수가 모두 선언되어 있어야 한다."""
    text = _css_text()
    required_vars = [
        "--phase-dd",
        "--phase-im",
        "--phase-ts",
        "--phase-xx",
        "--phase-failed",
        "--phase-bypass",
        "--phase-pending",
        "--critical",
    ]
    missing = [v for v in required_vars if v not in text]
    assert not missing, f"다음 CSS 변수가 style.css에 없습니다: {missing}"


def test_phase_data_attr_mapping():
    """_phase_data_attr 이 7가지 상태 코드를 올바르게 매핑해야 한다."""
    fn = _phase_data_attr
    cases = [
        ("[dd]",    "dd"),
        ("[im]",    "im"),
        ("[ts]",    "ts"),
        ("[xx]",    "xx"),
        ("failed",  "failed"),
        ("bypass",  "bypass"),
        ("pending", "pending"),
    ]
    for input_val, expected in cases:
        result = fn(input_val)
        assert result == expected, (
            f"_phase_data_attr({input_val!r}) == {result!r}, expected {expected!r}"
        )


def test_wcag_contrast_comments():
    """style.css 내에 WCAG AA contrast 근거 주석이 있어야 한다.

    'WCAG AA' 또는 '4.5:1' 키워드 중 하나 이상이 포함되어야 한다.
    """
    text = _css_text()
    has_wcag_aa = "WCAG AA" in text
    has_ratio = "4.5:1" in text
    assert has_wcag_aa or has_ratio, (
        "style.css에 WCAG AA contrast 근거 주석('WCAG AA' 또는 '4.5:1')이 없습니다."
    )


def test_phase_data_attr_unknown_input():
    """_phase_data_attr 에 알 수 없는 입력이 들어오면 'pending' 을 반환해야 한다.

    Note: 공백 포함 유효 코드(예: '  [dd]  ')는 strip 후 매핑되므로 'pending'이 아닌
    해당 매핑값을 반환한다. 본 테스트는 완전히 미지의 입력만 검증한다.
    """
    unknown_cases = ["", "[ ]", "UNKNOWN", "dd", "im"]  # 대괄호 없는 코드도 미지 입력
    for val in unknown_cases:
        result = _phase_data_attr(val)
        assert result == "pending", (
            f"_phase_data_attr({val!r}) == {result!r}, expected 'pending'"
        )


def test_existing_variables_untouched():
    """기존 CSS 변수(--run, --done, --fail, --accent, --pending, --ink-*, --bg-*)가
    style.css에 여전히 존재해야 한다 (값 변경 금지 제약의 존재 확인).

    본 테스트는 기존 변수명의 존재만 확인한다 (값은 TSK-01-02 스냅샷 테스트가 담당).
    """
    text = _css_text()
    # 기존 변수들이 삭제되지 않았음을 확인
    legacy_vars = ["--run", "--done", "--fail", "--accent", "--pending"]
    missing = [v for v in legacy_vars if v not in text]
    assert not missing, (
        f"기존 CSS 변수가 style.css에서 삭제되었습니다: {missing}"
    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
