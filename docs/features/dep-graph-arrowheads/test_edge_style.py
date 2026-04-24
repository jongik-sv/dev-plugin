"""
TDD 단위 테스트 — dep-graph-arrowheads feature
graph-client.js edge 스타일에 arrow-scale, target-distance-from-node 추가 확인
"""
import re
import sys
from pathlib import Path

VENDOR_PATH = Path(__file__).parent.parent.parent.parent / "skills/dev-monitor/vendor/graph-client.js"


def read_js():
    return VENDOR_PATH.read_text(encoding="utf-8")


def get_edge_selector_block(js: str) -> str:
    """selector: "edge" 블록을 추출한다."""
    # edge selector 블록의 style 내용 추출
    match = re.search(
        r'selector:\s*["\']edge["\'].*?style:\s*\{(.*?)\}',
        js,
        re.DOTALL,
    )
    if not match:
        return ""
    return match.group(1)


def test_arrow_scale_present():
    """arrow-scale: 1.0 초과 값이 edge selector style에 존재해야 한다 (화살표 머리 가시성 확보)."""
    js = read_js()
    block = get_edge_selector_block(js)
    assert block, "edge selector style block을 찾을 수 없습니다"
    match = re.search(r'"arrow-scale"\s*:\s*(\d+(?:\.\d+)?)', block)
    assert match, '"arrow-scale" 속성이 edge selector style에 없습니다'
    value = float(match.group(1))
    assert value > 1.0, f'"arrow-scale" 값이 1.0 이하입니다: {value}'
    print(f"  [PASS] arrow-scale = {value}")


def test_target_distance_from_node_present():
    """target-distance-from-node: 1 이상의 값이 edge selector style에 존재해야 한다."""
    js = read_js()
    block = get_edge_selector_block(js)
    assert block, "edge selector style block을 찾을 수 없습니다"
    match = re.search(r'"target-distance-from-node"\s*:\s*(\d+(?:\.\d+)?)', block)
    assert match, '"target-distance-from-node" 속성이 edge selector style에 없습니다'
    value = float(match.group(1))
    assert value >= 1, f'"target-distance-from-node" 값이 너무 작습니다: {value}'
    print(f"  [PASS] target-distance-from-node = {value}")


def test_target_arrow_color_has_fallback():
    """target-arrow-color가 data(color) 기반이거나 고정 색상으로 설정되어야 한다.
    최소 요건: edge selector style에 target-arrow-color 속성이 존재한다."""
    js = read_js()
    block = get_edge_selector_block(js)
    assert block, "edge selector style block을 찾을 수 없습니다"
    match = re.search(r'"target-arrow-color"', block)
    assert match, '"target-arrow-color" 속성이 edge selector style에 없습니다'
    print("  [PASS] target-arrow-color 속성 존재 확인")


def test_target_arrow_shape_is_triangle():
    """target-arrow-shape: triangle 이 edge selector style에 유지되어야 한다."""
    js = read_js()
    block = get_edge_selector_block(js)
    assert block, "edge selector style block을 찾을 수 없습니다"
    match = re.search(r'"target-arrow-shape"\s*:\s*["\']triangle["\']', block)
    assert match, '"target-arrow-shape": "triangle" 이 edge selector style에 없습니다'
    print("  [PASS] target-arrow-shape = triangle")


def run_all():
    tests = [
        test_arrow_scale_present,
        test_target_distance_from_node_present,
        test_target_arrow_color_has_fallback,
        test_target_arrow_shape_is_triangle,
    ]
    failed = 0
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {e}")
            failed += 1

    print(f"\n결과: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    print(f"대상 파일: {VENDOR_PATH}")
    if not VENDOR_PATH.exists():
        print("ERROR: graph-client.js 파일을 찾을 수 없습니다")
        sys.exit(1)
    sys.exit(run_all())
