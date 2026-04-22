"""Unit tests for dep-analysis.py --graph-stats extensions (TSK-03-02).

QA 체크리스트 항목을 매핑한다:

- fan_out[t]: children 역방향 수 (fan_in과 대칭)
- critical_path: longest path DP 계산 → {"nodes": [...], "edges": [...]}
- bottleneck_ids: fan_in >= 3 or fan_out >= 3인 task ID 목록
- --graph-stats 빈 입력 → 기본값 반환

실행: pytest -q scripts/test_dep_analysis_critical_path.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# dep-analysis.py module loader
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_DEP_PATH = _THIS_DIR / "dep-analysis.py"
_spec = importlib.util.spec_from_file_location("dep_analysis", _DEP_PATH)
dep_analysis = importlib.util.module_from_spec(_spec)
sys.modules["dep_analysis"] = dep_analysis
_spec.loader.exec_module(dep_analysis)

compute_graph_stats = dep_analysis.compute_graph_stats


def _items(*task_specs):
    """Helper: list of {tsk_id, depends, status} dicts."""
    result = []
    for spec in task_specs:
        if isinstance(spec, str):
            result.append({"tsk_id": spec, "depends": "-"})
        else:
            tsk_id, depends = spec
            result.append({
                "tsk_id": tsk_id,
                "depends": depends if depends else "-",
            })
    return result


# ---------------------------------------------------------------------------
# fan_out: 각 task가 몇 개 task의 depends에 등장하는가
# ---------------------------------------------------------------------------


class TestFanOut(unittest.TestCase):
    """fan_out_map: children 역방향 카운트 (fan_in의 대칭)."""

    def test_fan_out_present_in_result(self):
        """compute_graph_stats 결과에 fan_out_map 키가 존재해야 한다."""
        items = _items("TSK-01-01", ("TSK-01-02", "TSK-01-01"))
        result = compute_graph_stats(items)
        self.assertIn("fan_out_map", result, "fan_out_map 키 없음 (구현 전)")

    def test_fan_out_zero_for_leaf(self):
        """의존하는 task가 없는 leaf node의 fan_out == 0."""
        items = _items("TSK-01-01", ("TSK-01-02", "TSK-01-01"))
        result = compute_graph_stats(items)
        fan_out = result.get("fan_out_map", {})
        # TSK-01-02 is a leaf (nothing depends on it)
        self.assertEqual(fan_out.get("TSK-01-02", 0), 0)

    def test_fan_out_counts_children(self):
        """TSK-01-01에 TSK-01-02, TSK-01-03이 의존 → fan_out == 2."""
        items = _items(
            "TSK-01-01",
            ("TSK-01-02", "TSK-01-01"),
            ("TSK-01-03", "TSK-01-01"),
        )
        result = compute_graph_stats(items)
        fan_out = result.get("fan_out_map", {})
        self.assertEqual(fan_out.get("TSK-01-01", 0), 2)

    def test_fan_out_symmetric_with_fan_in(self):
        """fan_out[X] == 해당 X를 depends로 지정한 task 수 == fan_in[X].

        즉 fan_in_map이 없는 경우엔 fan_out_map을 통해 fan_in 방향을 역으로 검증.
        """
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-A"),
            ("TSK-D", "TSK-A"),
        )
        result = compute_graph_stats(items)
        fan_out = result.get("fan_out_map", {})
        # 3 tasks depend on TSK-A
        self.assertEqual(fan_out.get("TSK-A", 0), 3)
        # TSK-B,C,D are leaves
        for leaf in ("TSK-B", "TSK-C", "TSK-D"):
            self.assertEqual(fan_out.get(leaf, 0), 0)


# ---------------------------------------------------------------------------
# critical_path: longest path via DP
# ---------------------------------------------------------------------------


class TestCriticalPath(unittest.TestCase):
    """critical_path: DAG의 longest path 계산."""

    def test_critical_path_key_present(self):
        """compute_graph_stats 결과에 critical_path 키가 존재해야 한다."""
        items = _items("TSK-01-01")
        result = compute_graph_stats(items)
        self.assertIn("critical_path", result, "critical_path 키 없음 (구현 전)")

    def test_critical_path_has_nodes_and_edges(self):
        """critical_path는 {'nodes': [...], 'edges': [...]} 구조여야 한다."""
        items = _items("TSK-01-01", ("TSK-01-02", "TSK-01-01"))
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        self.assertIn("nodes", cp, "critical_path에 nodes 없음")
        self.assertIn("edges", cp, "critical_path에 edges 없음")

    def test_critical_path_single_node(self):
        """Task 1개 → critical_path.nodes == ['TSK-01-01']."""
        items = _items("TSK-01-01")
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        self.assertEqual(cp.get("nodes"), ["TSK-01-01"])

    def test_critical_path_linear_chain(self):
        """A → B → C 직선 체인 → critical_path.nodes == [A, B, C]."""
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-B"),
        )
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        nodes = cp.get("nodes", [])
        self.assertEqual(len(nodes), 3, f"노드 수 불일치: {nodes}")
        self.assertIn("TSK-A", nodes)
        self.assertIn("TSK-B", nodes)
        self.assertIn("TSK-C", nodes)

    def test_critical_path_longest_branch(self):
        """두 갈래 중 긴 쪽이 critical path에 포함된다.

        A → B → C  (길이 3)
        A → D      (길이 2)
        B,C가 critical path.
        """
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-B"),
            ("TSK-D", "TSK-A"),
        )
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        nodes = cp.get("nodes", [])
        # The longest path goes through TSK-A, TSK-B, TSK-C
        self.assertIn("TSK-C", nodes, f"longest branch end not in critical path: {nodes}")
        # TSK-D is the shorter branch — might or might not be included depending on impl
        # but if both paths have same length root, TSK-D should NOT be in place of TSK-C

    def test_critical_path_length_equals_max_chain_depth(self):
        """critical_path.nodes 길이 == max_chain_depth."""
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-B"),
        )
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        nodes = cp.get("nodes", [])
        self.assertEqual(len(nodes), result.get("max_chain_depth", -1),
                         "critical_path 길이가 max_chain_depth와 다름")

    def test_critical_path_empty_input(self):
        """빈 입력 → critical_path.nodes == []."""
        result = compute_graph_stats([])
        cp = result.get("critical_path", {})
        self.assertEqual(cp.get("nodes", []), [])

    def test_critical_path_alphabetical_tiebreak(self):
        """동일 길이 경로 동점 시 알파벳 순서 작은 것이 우선 선택된다.

        ROOT → A (길이 2)
        ROOT → B (길이 2)
        ROOT + A (알파벳 우선) 가 선택되어야 한다.
        """
        items = _items(
            "ROOT",
            ("TSK-A", "ROOT"),
            ("TSK-B", "ROOT"),
        )
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        nodes = cp.get("nodes", [])
        if len(nodes) == 2:
            self.assertEqual(nodes[-1], "TSK-A", f"알파벳 tiebreak 실패: {nodes}")

    def test_critical_path_edges_connect_consecutive_nodes(self):
        """critical_path.edges가 nodes의 연속 쌍을 연결한다."""
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-B"),
        )
        result = compute_graph_stats(items)
        cp = result.get("critical_path", {})
        nodes = cp.get("nodes", [])
        edges = cp.get("edges", [])
        if len(nodes) >= 2 and edges:
            # At least one edge should connect consecutive nodes
            edge_pairs = {(e.get("source"), e.get("target")) for e in edges}
            for i in range(len(nodes) - 1):
                pair = (nodes[i], nodes[i + 1])
                self.assertIn(pair, edge_pairs, f"연속 노드 엣지 없음: {pair}")


# ---------------------------------------------------------------------------
# bottleneck_ids: fan_in >= 3 or fan_out >= 3
# ---------------------------------------------------------------------------


class TestBottleneckIds(unittest.TestCase):
    """bottleneck_ids: fan_in >= 3 or fan_out >= 3인 task ID 목록."""

    def test_bottleneck_ids_key_present(self):
        """compute_graph_stats 결과에 bottleneck_ids 키가 존재해야 한다."""
        items = _items("TSK-01-01")
        result = compute_graph_stats(items)
        self.assertIn("bottleneck_ids", result, "bottleneck_ids 키 없음 (구현 전)")

    def test_no_bottleneck_for_small_graph(self):
        """의존 수 < 3인 경우 bottleneck_ids는 빈 리스트."""
        items = _items(
            "TSK-A",
            ("TSK-B", "TSK-A"),
            ("TSK-C", "TSK-A"),  # fan_out[A] == 2, 임계값 미달
        )
        result = compute_graph_stats(items)
        bottlenecks = result.get("bottleneck_ids", [])
        self.assertNotIn("TSK-A", bottlenecks)

    def test_bottleneck_by_fan_in(self):
        """fan_in >= 3이면 bottleneck_ids에 포함."""
        # TSK-E는 A, B, C, D가 모두 의존 → fan_in[E] == 4
        items = _items(
            "TSK-E",
            ("TSK-A", "TSK-E"),
            ("TSK-B", "TSK-E"),
            ("TSK-C", "TSK-E"),
            ("TSK-D", "TSK-E"),
        )
        result = compute_graph_stats(items)
        bottlenecks = result.get("bottleneck_ids", [])
        self.assertIn("TSK-E", bottlenecks, f"fan_in >= 3인 TSK-E가 bottleneck에 없음: {bottlenecks}")

    def test_bottleneck_by_fan_out(self):
        """fan_out >= 3이면 bottleneck_ids에 포함."""
        # TSK-ROOT는 A, B, C가 의존 → fan_out[ROOT] == 3
        items = _items(
            "TSK-ROOT",
            ("TSK-A", "TSK-ROOT"),
            ("TSK-B", "TSK-ROOT"),
            ("TSK-C", "TSK-ROOT"),
        )
        result = compute_graph_stats(items)
        bottlenecks = result.get("bottleneck_ids", [])
        self.assertIn("TSK-ROOT", bottlenecks, f"fan_out >= 3인 TSK-ROOT가 bottleneck에 없음: {bottlenecks}")

    def test_bottleneck_threshold_is_3(self):
        """fan_in/fan_out == 2이면 bottleneck에 포함되지 않는다 (임계값 3)."""
        items = _items(
            "TSK-HUB",
            ("TSK-A", "TSK-HUB"),
            ("TSK-B", "TSK-HUB"),  # fan_out[HUB] == 2
        )
        result = compute_graph_stats(items)
        bottlenecks = result.get("bottleneck_ids", [])
        self.assertNotIn("TSK-HUB", bottlenecks)

    def test_bottleneck_no_duplicates(self):
        """fan_in >= 3 AND fan_out >= 3이어도 bottleneck_ids에 한 번만 등장."""
        # Create a node that both has many dependents (fan_in) and many children (fan_out)
        items = _items(
            "TSK-ROOT",
            "TSK-X",
            "TSK-Y",
            "TSK-Z",
            ("TSK-HUB", "TSK-ROOT, TSK-X, TSK-Y, TSK-Z"),  # fan_in[HUB] == 4
            ("TSK-A", "TSK-HUB"),
            ("TSK-B", "TSK-HUB"),
            ("TSK-C", "TSK-HUB"),  # fan_out[HUB] == 3
        )
        result = compute_graph_stats(items)
        bottlenecks = result.get("bottleneck_ids", [])
        count = bottlenecks.count("TSK-HUB")
        self.assertEqual(count, 1, f"TSK-HUB가 bottleneck_ids에 중복: {bottlenecks}")


# ---------------------------------------------------------------------------
# --graph-stats empty input baseline
# ---------------------------------------------------------------------------


class TestGraphStatsEmptyInput(unittest.TestCase):
    """빈 입력 → 기본값 반환 (회귀 방지)."""

    def test_empty_has_critical_path_key(self):
        result = compute_graph_stats([])
        self.assertIn("critical_path", result)

    def test_empty_has_fan_out_map_key(self):
        result = compute_graph_stats([])
        self.assertIn("fan_out_map", result)

    def test_empty_has_bottleneck_ids_key(self):
        result = compute_graph_stats([])
        self.assertIn("bottleneck_ids", result)

    def test_empty_critical_path_nodes_empty(self):
        result = compute_graph_stats([])
        cp = result.get("critical_path", {})
        self.assertEqual(cp.get("nodes", []), [])
        self.assertEqual(cp.get("edges", []), [])

    def test_empty_bottleneck_ids_empty(self):
        result = compute_graph_stats([])
        self.assertEqual(result.get("bottleneck_ids", []), [])

    def test_empty_fan_out_map_empty(self):
        result = compute_graph_stats([])
        self.assertEqual(result.get("fan_out_map", {}), {})


if __name__ == "__main__":
    unittest.main()
