"""
TSK-05-01: Fold 영속성 JS + patchSection 훅 확장 — 단위 테스트

브라우저 비의존 방식으로 _DASHBOARD_JS 문자열 내 코드 존재 및 패턴을 검증한다.
pytest -q scripts/test_monitor_fold.py
"""
import re
import os
import pytest

# TSK-01-03: JS가 app.js로 추출됨 — app.js를 직접 읽는다
_SERVER_PATH = os.path.join(os.path.dirname(__file__), "monitor-server.py")
_APP_JS_PATH = os.path.join(os.path.dirname(__file__), "monitor_server", "static", "app.js")


def _load_dashboard_js():
    """monitor-server 모듈 또는 monitor_server/core.py에서 _DASHBOARD_JS 문자열을 추출한다.

    [core-dashboard-asset-split:C1-2] 외부 파일 우선, core.py regex-parse fallback.
    """
    _CORE_PATH = os.path.join(os.path.dirname(_SERVER_PATH), "monitor_server", "core.py")
    # 외부 파일 우선
    _static_js = os.path.join(os.path.dirname(_CORE_PATH), "static", "dashboard.js")
    if os.path.exists(_static_js):
        with open(_static_js, encoding="utf-8") as f:
            return f.read()

    # Legacy fallback (삼중 따옴표 블록)
    def _search_in_file(path):
        try:
            with open(path, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return None
        m = re.search(r'_DASHBOARD_JS\s*=\s*"""(.*?)"""', source, re.DOTALL)
        if not m:
            m = re.search(r"_DASHBOARD_JS\s*=\s*'''(.*?)'''", source, re.DOTALL)
        return m.group(1) if m else None

    result = _search_in_file(_SERVER_PATH)
    if result is None:
        result = _search_in_file(_CORE_PATH)
    if result is None:
        pytest.fail("_DASHBOARD_JS 변수를 monitor-server.py 또는 monitor_server/core.py에서 찾을 수 없습니다.")
    return result


def _load_server_source():
    """monitor-server.py + monitor_server/core.py + renderers/*.py 전체 소스를 합쳐 반환한다.

    TSK-02-03 이후 구현이 core.py로 이전되었으므로, 두 파일을 합친 소스로 검색해야
    기존 테스트가 함수 정의를 찾을 수 있다.
    core-renderer-split 이후 일부 렌더러 함수가 renderers/ 하위 모듈로 이전되므로
    renderers/*.py 도 포함한다.
    """
    _CORE_PATH = os.path.join(os.path.dirname(_SERVER_PATH), "monitor_server", "core.py")
    _RENDERERS_DIR = os.path.join(os.path.dirname(_SERVER_PATH), "monitor_server", "renderers")
    parts = []
    # renderers/*.py를 먼저 추가: 이관된 함수의 전체 본문이 core.py의 thin-wrapper보다
    # 먼저 검색되도록 한다. (core-renderer-split 이후 SSOT는 renderers/*.py)
    if os.path.isdir(_RENDERERS_DIR):
        import glob as _glob
        for rpath in sorted(_glob.glob(os.path.join(_RENDERERS_DIR, "*.py"))):
            try:
                with open(rpath, encoding="utf-8") as f:
                    parts.append(f.read())
            except OSError:
                pass
    for path in (_SERVER_PATH, _CORE_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                parts.append(f.read())
        except OSError:
            pass
    return "\n".join(parts)


def _extract_function_body(source, func_name, max_chars=4000):
    """source에서 func_name 함수 시작부터 max_chars까지 반환한다."""
    start = source.find(f"function {func_name}(")
    if start == -1:
        return None
    return source[start : start + max_chars]


def _extract_patchSection_body(js):
    """patchSection 함수 전체 블록을 반환한다.

    patchSection은 여러 개의 중첩 if 분기(hdr, wp-cards 등)를 가지므로
    단순 정규식으로 끝 위치를 찾기 어렵다.
    대신 patchSection 시작부터 다음 주석 섹션 헤더 또는 다음 function까지를 반환한다.
    """
    start = js.find("function patchSection(")
    if start == -1:
        return None
    # "/* ---- drawer control" 이 patchSection 직후에 위치함
    end_markers = [
        "/* ---- drawer control",
        "\n  function _setDrawerOpen(",
    ]
    end = -1
    for marker in end_markers:
        pos = js.find(marker, start)
        if pos != -1:
            if end == -1 or pos < end:
                end = pos
    if end == -1:
        return js[start : start + 4000]
    return js[start:end]


@pytest.fixture(scope="module")
def js():
    return _load_dashboard_js()


@pytest.fixture(scope="module")
def server_source():
    return _load_server_source()


# ---------------------------------------------------------------------------
# test_fold_localstorage_write
# AC-22: toggle 시 localStorage 키 값 정상 저장
# _DASHBOARD_JS에 writeFold 함수 정의와 localStorage.setItem 호출이 존재한다.
# ---------------------------------------------------------------------------
def test_fold_localstorage_write(js):
    assert "writeFold" in js, "_DASHBOARD_JS에 writeFold 함수가 없습니다."
    assert "localStorage.setItem" in js, "_DASHBOARD_JS에 localStorage.setItem 호출이 없습니다."


# ---------------------------------------------------------------------------
# test_fold_restore_on_patch
# AC-23: 5초 auto-refresh 후 접힌 상태 유지
# patchSection 함수 내에 applyFoldStates 및 bindFoldListeners 호출이 존재하며,
# wp-cards 관련 분기 내에 위치한다.
# ---------------------------------------------------------------------------
def test_fold_restore_on_patch(js):
    # patchSection 함수가 존재해야 함
    assert "patchSection" in js, "_DASHBOARD_JS에 patchSection 함수가 없습니다."
    assert "applyFoldStates" in js, "_DASHBOARD_JS에 applyFoldStates 호출이 없습니다."
    assert "bindFoldListeners" in js, "_DASHBOARD_JS에 bindFoldListeners 호출이 없습니다."

    patch_body_region = _extract_patchSection_body(js)
    assert patch_body_region is not None, "patchSection 함수를 찾을 수 없습니다."

    assert "wp-cards" in patch_body_region, (
        "patchSection 함수에 'wp-cards' 분기가 없습니다."
    )
    assert "applyFoldStates" in patch_body_region, (
        "patchSection 함수에 applyFoldStates 호출이 없습니다."
    )
    assert "bindFoldListeners" in patch_body_region, (
        "patchSection 함수에 bindFoldListeners 호출이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_fold_bind_idempotent
# __foldBound 중복 방지 패턴 검증
# ---------------------------------------------------------------------------
def test_fold_bind_idempotent(js):
    # TSK-00-01: _foldBound(단일 언더스코어) 또는 __foldBound(이중) 모두 허용
    has_flag = "_foldBound" in js or "__foldBound" in js
    assert has_flag, (
        "_DASHBOARD_JS에 _foldBound / __foldBound 플래그가 없습니다 (중복 리스너 방지 패턴 미구현)."
    )
    # bindFoldListeners 함수 내에 플래그 확인 패턴이 있어야 함
    bind_region = _extract_function_body(js, "bindFoldListeners", 800)
    assert bind_region is not None, "bindFoldListeners 함수가 없습니다."
    has_flag_in_bind = "_foldBound" in bind_region or "__foldBound" in bind_region
    assert has_flag_in_bind, (
        "bindFoldListeners 함수 내에 _foldBound / __foldBound 플래그 확인이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_fold_key_prefix
# FOLD_KEY_PREFIX 상수 정의 검증
# ---------------------------------------------------------------------------
def test_fold_key_prefix(js):
    assert "FOLD_KEY_PREFIX" in js, "_DASHBOARD_JS에 FOLD_KEY_PREFIX 상수가 없습니다."
    assert "dev-monitor:fold:" in js, (
        "_DASHBOARD_JS에 'dev-monitor:fold:' 키 프리픽스 값이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_fold_apply_states
# applyFoldStates 함수가 details[data-wp]를 쿼리하고
# removeAttribute('open') 또는 setAttribute('open','') 호출을 포함한다.
# ---------------------------------------------------------------------------
def test_fold_apply_states(js):
    apply_region = _extract_function_body(js, "applyFoldStates", 800)
    assert apply_region is not None, "applyFoldStates 함수가 없습니다."
    # TSK-00-01: 범용화로 셀렉터가 [data-fold-key]로 변경됨. 구 details[data-wp]도 허용.
    has_selector = "details[data-wp]" in apply_region or "[data-fold-key]" in apply_region
    assert has_selector, (
        "applyFoldStates가 'details[data-wp]' 또는 '[data-fold-key]' 셀렉터를 쿼리하지 않습니다."
    )
    has_remove = "removeAttribute('open')" in apply_region or 'removeAttribute("open")' in apply_region
    has_set = "setAttribute('open'" in apply_region or 'setAttribute("open"' in apply_region
    assert has_remove or has_set, (
        "applyFoldStates에 removeAttribute('open') 또는 setAttribute('open',...) 호출이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_fold_init_hook
# init() 함수 내 startMainPoll() 직전에 applyFoldStates 호출이 존재한다.
# ---------------------------------------------------------------------------
def test_fold_init_hook(js):
    init_region = _extract_function_body(js, "init", 1500)
    assert init_region is not None, "init 함수가 없습니다."
    assert "applyFoldStates" in init_region, (
        "init 함수 내에 applyFoldStates 호출이 없습니다."
    )
    assert "bindFoldListeners" in init_region, (
        "init 함수 내에 bindFoldListeners 호출이 없습니다."
    )
    # startMainPoll() 보다 앞에 applyFoldStates가 등장해야 함
    apply_pos = init_region.find("applyFoldStates")
    start_poll_pos = init_region.find("startMainPoll()")
    assert apply_pos != -1 and start_poll_pos != -1, (
        "init 내 applyFoldStates 또는 startMainPoll()을 찾을 수 없습니다."
    )
    assert apply_pos < start_poll_pos, (
        "init 함수에서 applyFoldStates가 startMainPoll() 이후에 위치합니다 (순서 오류)."
    )


# ---------------------------------------------------------------------------
# test_fold_try_catch
# readFold와 writeFold 각각에 try{...}catch 블록이 존재한다.
# ---------------------------------------------------------------------------
def test_fold_try_catch(js):
    # readFold 내 try/catch
    read_region = _extract_function_body(js, "readFold", 400)
    assert read_region is not None, "readFold 함수가 없습니다."
    assert "try{" in read_region or "try {" in read_region, (
        "readFold 함수에 try/catch 블록이 없습니다."
    )
    assert "catch(" in read_region, (
        "readFold 함수에 catch 블록이 없습니다."
    )
    # writeFold 내 try/catch
    write_region = _extract_function_body(js, "writeFold", 400)
    assert write_region is not None, "writeFold 함수가 없습니다."
    assert "try{" in write_region or "try {" in write_region, (
        "writeFold 함수에 try/catch 블록이 없습니다."
    )
    assert "catch(" in write_region, (
        "writeFold 함수에 catch 블록이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_fold_server_default_open
# 서버 _section_wp_cards Python 함수가 details 요소를 open attribute와 함께 렌더링한다.
# (서버 계약 변경 없음 확인)
# ---------------------------------------------------------------------------
def test_fold_server_default_open(server_source):
    # _section_wp_cards 함수 내에 <details open 또는 <details ... open이 있어야 함
    func_start = server_source.find("def _section_wp_cards(")
    assert func_start != -1, "_section_wp_cards 함수를 찾을 수 없습니다."
    # 다음 def 까지
    next_def = server_source.find("\ndef ", func_start + 1)
    if next_def == -1:
        func_region = server_source[func_start:]
    else:
        func_region = server_source[func_start:next_def]
    # <details ... open 패턴이 있어야 함 (속성 순서 무관)
    has_details_open = bool(
        re.search(r"<details\b[^>]*\bopen\b", func_region)
        or re.search(r"details[^'\"]*open", func_region)
    )
    assert has_details_open, (
        "_section_wp_cards 함수에서 <details ... open> 기본값 렌더링 패턴이 없습니다 "
        "(서버 계약 변경 금지)."
    )


# ---------------------------------------------------------------------------
# 통합 테스트 (브라우저 필요 — skip 마커)
# AC-23, AC-24는 브라우저 자동화로만 검증 가능하므로 dev-test 단계에서 수행
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="브라우저 필요 — AC-23 (5초 auto-refresh 후 fold 유지). dev-test E2E에서 검증.")
def test_fold_restore_after_autorefresh():
    """5초 auto-refresh 후 접힌 WP 카드가 다시 펼쳐지지 않는다 (AC-23)."""
    pass


@pytest.mark.skip(reason="브라우저 필요 — AC-24 (F5 하드 리로드 후 fold 유지). dev-test E2E에서 검증.")
def test_fold_restore_after_hard_reload():
    """하드 리로드(F5) 후 접힌 상태가 유지된다 (AC-24)."""
    pass
