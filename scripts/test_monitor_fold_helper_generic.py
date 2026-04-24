"""
TSK-00-01: 범용 fold 헬퍼 단위 테스트

_DASHBOARD_JS 소스 grep 방식으로 다음을 검증한다:
- readFold(key, defaultOpen) 시그니처
- querySelectorAll('[data-fold-key]') 셀렉터
- data-fold-default-open 속성 처리
- _foldBound 플래그 (중복 바인딩 방지)
- localStorage 키 prefix 유지
pytest -q scripts/test_monitor_fold_helper_generic.py
"""
import re
import os
import pytest

_SERVER_PATH = os.path.join(os.path.dirname(__file__), "monitor-server.py")
_APP_JS_PATH = os.path.join(os.path.dirname(__file__), "monitor_server", "static", "app.js")


_CORE_PATH = os.path.join(os.path.dirname(_SERVER_PATH), "monitor_server", "core.py")


def _load_dashboard_js():
    """monitor-server.py 또는 monitor_server/core.py에서 _DASHBOARD_JS를 추출한다."""
    for path in (_SERVER_PATH, _CORE_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            continue
        m = re.search(r'_DASHBOARD_JS\s*=\s*"""(.*?)"""', source, re.DOTALL)
        if not m:
            m = re.search(r"_DASHBOARD_JS\s*=\s*'''(.*?)'''", source, re.DOTALL)
        if m:
            return m.group(1)
    pytest.fail("_DASHBOARD_JS 변수를 monitor-server.py 또는 monitor_server/core.py에서 찾을 수 없습니다.")


def _load_server_source():
    """monitor-server.py + monitor_server/core.py 합산 소스를 반환한다."""
    parts = []
    for path in (_SERVER_PATH, _CORE_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                parts.append(f.read())
        except OSError:
            pass
    return "\n".join(parts)


def _extract_function_body(source, func_name, max_chars=1000):
    start = source.find(f"function {func_name}(")
    if start == -1:
        return None
    return source[start: start + max_chars]


@pytest.fixture(scope="module")
def js():
    return _load_dashboard_js()


@pytest.fixture(scope="module")
def server_source():
    return _load_server_source()


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_generic_data_key
# readFold(key, defaultOpen) 시그니처: 두 번째 파라미터로 기본값을 받는다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_read_fold_signature(js):
    """readFold 함수가 두 파라미터(key, defaultOpen)를 받는 시그니처를 가진다."""
    # function readFold(key, defaultOpen) 또는 (key,defaultOpen) 형태
    pattern = r'function readFold\s*\(\s*\w+\s*,\s*\w+'
    assert re.search(pattern, js), (
        "readFold 함수가 (key, defaultOpen) 형태의 두 파라미터 시그니처를 갖지 않습니다."
    )


def test_monitor_fold_helper_read_fold_default_return(js):
    """readFold는 localStorage 미지정 시 defaultOpen 파라미터를 반환한다."""
    read_region = _extract_function_body(js, "readFold", 600)
    assert read_region is not None, "readFold 함수가 없습니다."
    # defaultOpen (두번째 파라미터)을 return 하는 패턴이 있어야 함
    # 정확한 파라미터 이름은 구현에 따라 다를 수 있으므로 패턴으로 검증
    # 가장 일반적인 패턴: null 또는 미지정 시 두 번째 인자 반환
    # readFold 함수 시그니처에서 두 번째 파라미터 이름 추출
    sig_m = re.search(r'function readFold\s*\(\s*(\w+)\s*,\s*(\w+)', js)
    assert sig_m is not None, "readFold 시그니처를 파싱할 수 없습니다."
    default_param = sig_m.group(2)
    # 함수 본문에서 default_param을 반환하는 패턴
    assert default_param in read_region, (
        f"readFold 함수 본문에 defaultOpen 파라미터({default_param})가 사용되지 않습니다."
    )
    assert "return" in read_region, "readFold 함수에 return 이 없습니다."


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_data_fold_key_selector
# applyFoldStates / bindFoldListeners 가 [data-fold-key] 셀렉터를 사용한다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_data_fold_key_selector(js):
    """applyFoldStates와 bindFoldListeners가 [data-fold-key] 셀렉터를 사용한다."""
    assert "[data-fold-key]" in js, (
        "_DASHBOARD_JS에 [data-fold-key] 셀렉터가 없습니다. "
        "applyFoldStates/bindFoldListeners가 범용 셀렉터를 사용해야 합니다."
    )
    apply_region = _extract_function_body(js, "applyFoldStates", 800)
    assert apply_region is not None, "applyFoldStates 함수가 없습니다."
    assert "[data-fold-key]" in apply_region, (
        "applyFoldStates 함수가 [data-fold-key] 셀렉터를 사용하지 않습니다."
    )

    bind_region = _extract_function_body(js, "bindFoldListeners", 800)
    assert bind_region is not None, "bindFoldListeners 함수가 없습니다."
    assert "[data-fold-key]" in bind_region, (
        "bindFoldListeners 함수가 [data-fold-key] 셀렉터를 사용하지 않습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_data_fold_default_open_attr
# applyFoldStates 가 data-fold-default-open 속성으로 기본값을 결정한다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_data_fold_default_open_attr(js):
    """applyFoldStates가 data-fold-default-open 속성을 기본값 결정에 사용한다."""
    apply_region = _extract_function_body(js, "applyFoldStates", 800)
    assert apply_region is not None, "applyFoldStates 함수가 없습니다."
    assert "data-fold-default-open" in apply_region, (
        "applyFoldStates 함수에 data-fold-default-open 속성 처리가 없습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_fold_bound_flag
# bindFoldListeners 가 _foldBound 플래그로 중복 바인딩을 방지한다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_fold_bound_flag(js):
    """bindFoldListeners가 _foldBound 플래그를 사용하여 중복 바인딩을 방지한다."""
    bind_region = _extract_function_body(js, "bindFoldListeners", 800)
    assert bind_region is not None, "bindFoldListeners 함수가 없습니다."
    # __foldBound 또는 _foldBound (design.md 명세: _foldBound)
    has_flag = "_foldBound" in bind_region or "__foldBound" in bind_region
    assert has_flag, (
        "bindFoldListeners 함수에 _foldBound (또는 __foldBound) 중복 방지 플래그가 없습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_key_prefix_preserved
# localStorage 키 prefix 'dev-monitor:fold:' 가 유지된다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_key_prefix_preserved(js):
    """기존 localStorage 키 prefix 'dev-monitor:fold:'가 유지된다."""
    assert "dev-monitor:fold:" in js, (
        "_DASHBOARD_JS에 'dev-monitor:fold:' 키 prefix가 없습니다. "
        "마이그레이션 없이 기존 키를 유지해야 합니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_write_fold_signature
# writeFold(key, open) 시그니처: 두 파라미터.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_write_fold_signature(js):
    """writeFold 함수가 (key, open) 두 파라미터를 받는 시그니처를 가진다."""
    pattern = r'function writeFold\s*\(\s*\w+\s*,\s*\w+'
    assert re.search(pattern, js), (
        "writeFold 함수가 (key, open) 두 파라미터 시그니처를 갖지 않습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_server_uses_data_fold_key
# _section_wp_cards Python 함수가 data-fold-key 속성을 렌더링한다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_server_uses_data_fold_key(server_source):
    """_section_wp_cards Python 함수가 data-fold-key 속성을 렌더링한다."""
    func_start = server_source.find("def _section_wp_cards(")
    assert func_start != -1, "_section_wp_cards 함수를 찾을 수 없습니다."
    next_def = server_source.find("\ndef ", func_start + 1)
    func_region = server_source[func_start:next_def] if next_def != -1 else server_source[func_start:]
    assert "data-fold-key" in func_region, (
        "_section_wp_cards 함수가 data-fold-key 속성을 렌더링하지 않습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_fold_helper_server_uses_data_fold_default_open
# _section_wp_cards Python 함수가 data-fold-default-open 속성도 렌더링한다.
# ---------------------------------------------------------------------------
def test_monitor_fold_helper_server_uses_data_fold_default_open(server_source):
    """_section_wp_cards Python 함수가 data-fold-default-open 속성을 렌더링한다 (기본 열림)."""
    func_start = server_source.find("def _section_wp_cards(")
    assert func_start != -1, "_section_wp_cards 함수를 찾을 수 없습니다."
    next_def = server_source.find("\ndef ", func_start + 1)
    func_region = server_source[func_start:next_def] if next_def != -1 else server_source[func_start:]
    assert "data-fold-default-open" in func_region, (
        "_section_wp_cards 함수가 data-fold-default-open 속성을 렌더링하지 않습니다."
    )
