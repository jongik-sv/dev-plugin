"""
TSK-00-01: 공용 spinner CSS 단위 테스트

monitor-server.py 인라인 CSS (_DASHBOARD_CSS) 에서
@keyframes spin 및 .spinner/.node-spinner 관련 규칙을 검증한다.
pytest -q scripts/test_monitor_shared_css.py
"""
import re
import os
import pytest

_SERVER_PATH = os.path.join(os.path.dirname(__file__), "monitor-server.py")


_CORE_PATH = os.path.join(os.path.dirname(_SERVER_PATH), "monitor_server", "core.py")


def _load_dashboard_css():
    """monitor-server.py 또는 monitor_server/core.py에서 DASHBOARD_CSS를 추출한다."""
    for path in (_SERVER_PATH, _CORE_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            continue
        # DASHBOARD_CSS = """...""" 또는 '''...''' 패턴 (언더스코어 없음)
        m = re.search(r'\bDASHBOARD_CSS\s*=\s*"""(.*?)"""', source, re.DOTALL)
        if not m:
            m = re.search(r"\bDASHBOARD_CSS\s*=\s*'''(.*?)'''", source, re.DOTALL)
        if m:
            return m.group(1)
    pytest.fail("DASHBOARD_CSS 변수를 monitor-server.py 또는 monitor_server/core.py에서 찾을 수 없습니다.")


@pytest.fixture(scope="module")
def css():
    return _load_dashboard_css()


# ---------------------------------------------------------------------------
# test_monitor_shared_css_has_spin_keyframe
# @keyframes spin 이 인라인 CSS에 정확히 1회 정의된다 (중복 금지).
# ---------------------------------------------------------------------------
def test_monitor_shared_css_has_spin_keyframe(css):
    count = css.count("@keyframes spin")
    assert count == 1, (
        f"@keyframes spin 이 _DASHBOARD_CSS 에 {count}회 정의되어 있습니다. 정확히 1회여야 합니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_shared_css_spin_keyframe_content
# @keyframes spin 블록에 transform: rotate(360deg) 가 포함된다.
# ---------------------------------------------------------------------------
def test_monitor_shared_css_spin_keyframe_content(css):
    spin_pos = css.find("@keyframes spin")
    assert spin_pos != -1, "@keyframes spin 이 없습니다."
    # 블록 끝 찾기 (다음 @keyframes 또는 400자 내)
    snippet = css[spin_pos: spin_pos + 300]
    assert "rotate(360deg)" in snippet, (
        "@keyframes spin 블록에 rotate(360deg) 가 없습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_shared_css_spinner_class
# .spinner 클래스 — display:none 기본값, animation: spin 포함.
# ---------------------------------------------------------------------------
def test_monitor_shared_css_spinner_class(css):
    assert ".spinner" in css, "_DASHBOARD_CSS에 .spinner 클래스가 없습니다."
    # .spinner 블록 추출 (간단 탐색)
    spinner_pos = css.find(".spinner")
    snippet = css[spinner_pos: spinner_pos + 400]
    assert "display:none" in snippet or "display: none" in snippet, (
        ".spinner 클래스에 display:none 기본값이 없습니다."
    )
    assert "animation" in snippet and "spin" in snippet, (
        ".spinner 클래스에 animation: spin 이 없습니다."
    )


# ---------------------------------------------------------------------------
# test_monitor_shared_css_node_spinner_class
# .node-spinner 클래스 선언이 존재한다.
# ---------------------------------------------------------------------------
def test_monitor_shared_css_node_spinner_class(css):
    assert ".node-spinner" in css, "_DASHBOARD_CSS에 .node-spinner 클래스가 없습니다."


# ---------------------------------------------------------------------------
# test_monitor_shared_css_spinner_visibility_rule
# TSK-04-01: .trow[data-running="true"] .badge .spinner-inline { display:inline-block } 규칙이 있다.
# (v4 row-level .spinner display 규칙은 TSK-04-01에서 제거됨 — .spinner-inline으로 이동)
# ---------------------------------------------------------------------------
def test_monitor_shared_css_spinner_visibility_rule(css):
    # TSK-04-01: spinner moved inside badge as .spinner-inline
    pattern = r'\.trow\[data-running=["\']true["\']\]\s*\.badge\s*\.spinner-inline'
    assert re.search(pattern, css), (
        '.trow[data-running="true"] .badge .spinner-inline 규칙이 _DASHBOARD_CSS에 없습니다.'
    )
    # display:inline-block 포함 여부
    trow_pos = css.find('.trow[data-running="true"] .badge .spinner-inline')
    snippet = css[trow_pos: trow_pos + 200] if trow_pos != -1 else ""
    assert "inline-block" in snippet, (
        '.trow[data-running="true"] .badge .spinner-inline 에 display:inline-block 이 없습니다.'
    )


# ---------------------------------------------------------------------------
# test_monitor_shared_css_node_spinner_visibility_rule
# .dep-node[data-running="true"] .node-spinner { display:inline-block; position:absolute } 규칙.
# ---------------------------------------------------------------------------
def test_monitor_shared_css_node_spinner_visibility_rule(css):
    pattern = r'\.dep-node\[data-running=["\']true["\']\]\s*\.node-spinner'
    assert re.search(pattern, css), (
        '.dep-node[data-running="true"] .node-spinner 규칙이 _DASHBOARD_CSS에 없습니다.'
    )
    dep_pos = next(
        (css.find(f'.dep-node[data-running={q}true{q}] .node-spinner') for q in ('"', "'") if css.find(f'.dep-node[data-running={q}true{q}] .node-spinner') != -1),
        -1
    )
    snippet = css[dep_pos: dep_pos + 200] if dep_pos != -1 else ""
    assert "inline-block" in snippet, (
        '.dep-node[data-running="true"] .node-spinner 에 display:inline-block 이 없습니다.'
    )
    assert "absolute" in snippet, (
        '.dep-node[data-running="true"] .node-spinner 에 position:absolute 가 없습니다.'
    )
