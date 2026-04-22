#!/usr/bin/env python3
"""Tests for dep-analysis.py --graph-stats extensions.

Covers:
  - test_dep_analysis_critical_path_linear
  - test_dep_analysis_critical_path_diamond
  - test_dep_analysis_fan_out
  - test_dep_analysis_bottleneck_ids

Also covers edge cases:
  - empty graph
  - single node
  - cycle detection (subprocess)
  - existing fields preserved (regression)
  - determinism
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# Dynamically load dep-analysis.py as a module
_SCRIPT = Path(__file__).parent / "dep-analysis.py"
_spec = importlib.util.spec_from_file_location("dep_analysis", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compute_graph_stats = _mod.compute_graph_stats
_compute_fan_out = getattr(_mod, "_compute_fan_out", None)
_compute_critical_path = getattr(_mod, "_compute_critical_path", None)
parse_depends = _mod.parse_depends


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _items(*edges):
    """Build items list from dependency edge tuples (dependent, dependency).

    edges: list of (dependent_id, dependency_id) or just plain id strings for
    isolated nodes.
    """
    node_map: dict[str, list[str]] = {}
    for edge in edges:
        if isinstance(edge, tuple):
            dep, src = edge  # dep depends on src
            node_map.setdefault(dep, [])
            node_map.setdefault(src, [])
            node_map[dep].append(src)
        else:
            node_map.setdefault(edge, [])
    return [
        {"tsk_id": tsk_id, "depends": ", ".join(deps) if deps else "-", "status": "[ ]"}
        for tsk_id, deps in sorted(node_map.items())
    ]


def _run_cli(items_json: str) -> dict:
    """Run dep-analysis.py --graph-stats via subprocess and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--graph-stats"],
        input=items_json,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI failed: stderr={result.stderr!r}"
    return json.loads(result.stdout)


def _run_cli_expect_error(items_json: str) -> subprocess.CompletedProcess:
    """Run dep-analysis.py --graph-stats and expect non-zero exit code."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--graph-stats"],
        input=items_json,
        capture_output=True,
        text=True,
    )
    return result


# ---------------------------------------------------------------------------
# AC-10: test_dep_analysis_critical_path_linear
# ---------------------------------------------------------------------------

def test_dep_analysis_critical_path_linear():
    """Linear chain A→B→C→D: critical_path.nodes == [A, B, C, D]."""
    # D depends C, C depends B, B depends A
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-B"),
        ("TSK-D", "TSK-C"),
    )
    result = compute_graph_stats(items)

    assert "critical_path" in result, "critical_path key missing"
    cp = result["critical_path"]
    assert "nodes" in cp
    assert "edges" in cp
    assert cp["nodes"] == ["TSK-A", "TSK-B", "TSK-C", "TSK-D"], (
        f"Expected linear path, got {cp['nodes']}"
    )
    assert len(cp["edges"]) == 3
    assert cp["edges"][0] == {"source": "TSK-A", "target": "TSK-B"}
    assert cp["edges"][1] == {"source": "TSK-B", "target": "TSK-C"}
    assert cp["edges"][2] == {"source": "TSK-C", "target": "TSK-D"}


def test_dep_analysis_critical_path_linear_cli():
    """Same as above but via CLI subprocess."""
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-B"),
        ("TSK-D", "TSK-C"),
    )
    result = _run_cli(json.dumps(items))
    cp = result["critical_path"]
    assert cp["nodes"] == ["TSK-A", "TSK-B", "TSK-C", "TSK-D"]
    assert len(cp["edges"]) == 3


# ---------------------------------------------------------------------------
# AC-11: test_dep_analysis_critical_path_diamond
# ---------------------------------------------------------------------------

def test_dep_analysis_critical_path_diamond():
    """Diamond graph: longer branch selected, tiebreak alphabetical.

    Topology:
      TSK-X → TSK-Y1 → TSK-Z   (X is root, Z merges)
      TSK-X → TSK-Y2 → TSK-Z
      TSK-Y0 → TSK-Y1           (makes Y0→Y1→Z longer than X→Y2→Z)

    So dist from root:
      TSK-X: 1 (root, no deps)
      TSK-Y0: 1 (root, no deps)
      TSK-Y2: 2 (depends on X)
      TSK-Y1: 3 (depends on X and Y0; max is Y0's path=2 + X's=1 → 1+max(1,1)+1=3
               ... actually dist[Y1] = 1 + max(dist[X], dist[Y0]) = 1 + max(1,1) = 2)

    Wait, let's think again:
      dist[node] = 1 + max(dist[p] for p in predecessors)
      TSK-X depends on nothing → dist=1
      TSK-Y0 depends on nothing → dist=1
      TSK-Y1 depends on TSK-X and TSK-Y0 → dist = 1 + max(1,1) = 2
      TSK-Y2 depends on TSK-X → dist = 1 + 1 = 2
      TSK-Z depends on TSK-Y1 and TSK-Y2 → dist = 1 + max(2,2) = 3

    So all paths to Z have dist=3. Tiebreak on parent alphabetical small:
      Y1 < Y2, so parent[Z] = Y1.
      For Y1: both X and Y0 give dist=1. alphabetical X < Y0, parent[Y1] = X.
    Path: X → Y1 → Z  (length 3)

    But wait — we need to verify longest PATH from a root. With Y0 as separate root:
    If we start from Y0: Y0 → Y1 → Z  (length 3)
    If we start from X: X → Y1 → Z OR X → Y2 → Z (both length 3)

    So the longest path is 3 nodes. But since X→Y1 uses parent[Y1]=X (not Y0),
    path traced from Z is Z → Y1 → X.  Reversed: X → Y1 → Z.

    Actually the design says longest path from a ROOT (fan_in==0) to a leaf.
    TSK-Y0 is also a root (fan_in=0). From Y0, path: Y0→Y1→Z = length 3.
    From X, path: X→Y1→Z or X→Y2→Z = length 3.

    Both give length 3. The endpoint Z has dist=3 in all cases.
    We pick endpoint alphabetical: Z is the only candidate.
    Then trace back: parent[Z] was Y1 (alphabetical before Y2).
    parent[Y1] was X (alphabetical before Y0).
    Path: [X, Y1, Z].
    """
    items = _items(
        ("TSK-Y1", "TSK-X"),
        ("TSK-Y1", "TSK-Y0"),
        ("TSK-Y2", "TSK-X"),
        ("TSK-Z", "TSK-Y1"),
        ("TSK-Z", "TSK-Y2"),
    )
    # Fix: _items creates all nodes from edges, but TSK-X and TSK-Y0 need to
    # be roots (no depends). The _items helper handles this.
    result = compute_graph_stats(items)
    cp = result["critical_path"]
    assert len(cp["nodes"]) >= 3, f"Expected at least 3 nodes, got {cp['nodes']}"
    # The path must end at TSK-Z
    assert cp["nodes"][-1] == "TSK-Z", f"Expected last node TSK-Z, got {cp['nodes']}"
    # Tiebreak: X < Y0 alphabetically, so parent[Y1] = X
    assert cp["nodes"] == ["TSK-X", "TSK-Y1", "TSK-Z"], (
        f"Expected [TSK-X, TSK-Y1, TSK-Z] with alphabetical tiebreak, got {cp['nodes']}"
    )


def test_dep_analysis_critical_path_diamond_strict_longer_branch():
    """When one branch is strictly longer, it wins (no tiebreak needed).

    Topology:
      TSK-START → TSK-LONG → TSK-LONG2 → TSK-END
      TSK-START → TSK-SHORT → TSK-END

    Longest path: START → LONG → LONG2 → END (4 nodes)
    """
    items = _items(
        ("TSK-LONG", "TSK-START"),
        ("TSK-LONG2", "TSK-LONG"),
        ("TSK-SHORT", "TSK-START"),
        ("TSK-END", "TSK-LONG2"),
        ("TSK-END", "TSK-SHORT"),
    )
    result = compute_graph_stats(items)
    cp = result["critical_path"]
    assert cp["nodes"] == ["TSK-START", "TSK-LONG", "TSK-LONG2", "TSK-END"], (
        f"Expected longest branch, got {cp['nodes']}"
    )


# ---------------------------------------------------------------------------
# AC-12: test_dep_analysis_fan_out
# ---------------------------------------------------------------------------

def test_dep_analysis_fan_out():
    """TSK-A is predecessor of B, C, D → fan_out[A]=3, fan_out[B/C/D]=0."""
    # B, C, D all depend on A
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-A"),
        ("TSK-D", "TSK-A"),
    )
    result = compute_graph_stats(items)

    assert "fan_out" in result, "fan_out key missing"
    fo = result["fan_out"]
    assert fo.get("TSK-A") == 3, f"Expected fan_out[A]=3, got {fo.get('TSK-A')}"
    assert fo.get("TSK-B", 0) == 0, f"Expected fan_out[B]=0, got {fo.get('TSK-B')}"
    assert fo.get("TSK-C", 0) == 0, f"Expected fan_out[C]=0, got {fo.get('TSK-C')}"
    assert fo.get("TSK-D", 0) == 0, f"Expected fan_out[D]=0, got {fo.get('TSK-D')}"


def test_dep_analysis_fan_out_cli():
    """CLI check for fan_out field."""
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-A"),
        ("TSK-D", "TSK-A"),
    )
    result = _run_cli(json.dumps(items))
    assert "fan_out" in result
    fo = result["fan_out"]
    assert fo.get("TSK-A") == 3


def test_dep_analysis_fan_out_zero_for_all():
    """No dependencies → all fan_out values are 0."""
    items = [
        {"tsk_id": "TSK-X", "depends": "-", "status": "[ ]"},
        {"tsk_id": "TSK-Y", "depends": "-", "status": "[ ]"},
    ]
    result = compute_graph_stats(items)
    fo = result["fan_out"]
    assert fo.get("TSK-X", 0) == 0
    assert fo.get("TSK-Y", 0) == 0


# ---------------------------------------------------------------------------
# AC-13: test_dep_analysis_bottleneck_ids
# ---------------------------------------------------------------------------

def test_dep_analysis_bottleneck_ids():
    """fan_in>=3 or fan_out>=3 → in bottleneck_ids; fan_in=2,fan_out=2 → not."""
    # TSK-HI-FAN-IN: 3 tasks depend on it → fan_in=3
    # TSK-HI-FAN-OUT: depends on 3 tasks → fan_out=3 (it has 3 predecessors,
    #   meaning 3 tasks have fan_out++ because this task depends on them —
    #   wait, fan_out[X] = number of tasks that depend on X (how many X feeds).
    #   So for HI-FAN-OUT to have fan_out=3, 3 other tasks must depend on it.
    # Let me re-read design:
    #   fan_out[t] = number of tasks that list t as a dependency (i.e., t feeds)
    # So:
    #   TSK-HI-FAN-IN: tasks A, B, C all depend on it → fan_in=3
    #   TSK-HI-FAN-OUT: tasks D, E, F all depend on it → fan_out=3
    #   TSK-MID: only 2 tasks depend on it (fan_in=2) AND only 2 tasks it feeds (fan_out=2)
    items = [
        # HI-FAN-IN is depended on by A, B, C → fan_in[HI-FAN-IN]=3
        {"tsk_id": "TSK-A", "depends": "TSK-HI-FAN-IN", "status": "[ ]"},
        {"tsk_id": "TSK-B", "depends": "TSK-HI-FAN-IN", "status": "[ ]"},
        {"tsk_id": "TSK-C", "depends": "TSK-HI-FAN-IN", "status": "[ ]"},
        {"tsk_id": "TSK-HI-FAN-IN", "depends": "-", "status": "[ ]"},
        # HI-FAN-OUT is depended on by D, E, F → fan_out[HI-FAN-OUT]=3
        # (fan_out[X] = how many tasks depend on X = how many X "outputs" to)
        {"tsk_id": "TSK-D", "depends": "TSK-HI-FAN-OUT", "status": "[ ]"},
        {"tsk_id": "TSK-E", "depends": "TSK-HI-FAN-OUT", "status": "[ ]"},
        {"tsk_id": "TSK-F", "depends": "TSK-HI-FAN-OUT", "status": "[ ]"},
        {"tsk_id": "TSK-HI-FAN-OUT", "depends": "-", "status": "[ ]"},
        # MID: only 2 tasks depend on it
        {"tsk_id": "TSK-P", "depends": "TSK-MID", "status": "[ ]"},
        {"tsk_id": "TSK-Q", "depends": "TSK-MID", "status": "[ ]"},
        {"tsk_id": "TSK-MID", "depends": "-", "status": "[ ]"},
    ]
    result = compute_graph_stats(items)

    assert "bottleneck_ids" in result, "bottleneck_ids key missing"
    bids = result["bottleneck_ids"]

    assert "TSK-HI-FAN-IN" in bids, f"Expected HI-FAN-IN in bottleneck_ids, got {bids}"
    assert "TSK-HI-FAN-OUT" in bids, f"Expected HI-FAN-OUT in bottleneck_ids, got {bids}"
    assert "TSK-MID" not in bids, f"Expected MID NOT in bottleneck_ids (fan_in=2, fan_out=2), got {bids}"

    # Must be alphabetically sorted
    assert bids == sorted(bids), f"bottleneck_ids not sorted: {bids}"


def test_dep_analysis_bottleneck_ids_cli():
    """CLI check for bottleneck_ids."""
    items = [
        {"tsk_id": "TSK-A", "depends": "TSK-ROOT", "status": "[ ]"},
        {"tsk_id": "TSK-B", "depends": "TSK-ROOT", "status": "[ ]"},
        {"tsk_id": "TSK-C", "depends": "TSK-ROOT", "status": "[ ]"},
        {"tsk_id": "TSK-ROOT", "depends": "-", "status": "[ ]"},
    ]
    result = _run_cli(json.dumps(items))
    assert "bottleneck_ids" in result
    assert "TSK-ROOT" in result["bottleneck_ids"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_dep_analysis_graph_stats_empty_graph():
    """Empty input → critical_path empty, fan_out empty, bottleneck_ids empty."""
    result = compute_graph_stats([])
    assert result["critical_path"] == {"nodes": [], "edges": []}
    assert result["fan_out"] == {}
    assert result["bottleneck_ids"] == []


def test_dep_analysis_graph_stats_single_node():
    """Single isolated node → critical_path has 1 node, no edges."""
    items = [{"tsk_id": "TSK-SOLO", "depends": "-", "status": "[ ]"}]
    result = compute_graph_stats(items)
    cp = result["critical_path"]
    assert cp["nodes"] == ["TSK-SOLO"]
    assert cp["edges"] == []
    fo = result["fan_out"]
    assert fo.get("TSK-SOLO", 0) == 0
    assert result["bottleneck_ids"] == []


def test_dep_analysis_cycle_detection_cli():
    """Cycle A→B→A: stderr should mention 'cycle' and exit code != 0."""
    items = [
        {"tsk_id": "TSK-A", "depends": "TSK-B", "status": "[ ]"},
        {"tsk_id": "TSK-B", "depends": "TSK-A", "status": "[ ]"},
    ]
    proc = _run_cli_expect_error(json.dumps(items))
    assert proc.returncode != 0, "Expected non-zero exit for cycle"
    assert "cycle" in proc.stderr.lower(), (
        f"Expected 'cycle' in stderr, got: {proc.stderr!r}"
    )


def test_dep_analysis_cycle_detection_raises():
    """compute_graph_stats raises ValueError for cyclic input."""
    items = [
        {"tsk_id": "TSK-A", "depends": "TSK-B", "status": "[ ]"},
        {"tsk_id": "TSK-B", "depends": "TSK-A", "status": "[ ]"},
    ]
    try:
        compute_graph_stats(items)
        assert False, "Expected ValueError for cycle"
    except ValueError as e:
        assert "cycle" in str(e).lower(), f"ValueError message should mention cycle: {e}"


# ---------------------------------------------------------------------------
# Regression: existing fields preserved
# ---------------------------------------------------------------------------

def test_dep_analysis_existing_fields_preserved():
    """New fields don't break existing: max_chain_depth, fan_in_top, etc."""
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-B"),
    )
    result = compute_graph_stats(items)
    for key in ["max_chain_depth", "total", "fan_in_top", "fan_in_ge_3_count",
                "diamond_patterns", "diamond_count", "review_candidates"]:
        assert key in result, f"Missing existing key: {key}"
    assert result["max_chain_depth"] == 3
    assert result["total"] == 3


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_dep_analysis_determinism():
    """Same input twice → same critical_path and bottleneck_ids."""
    items = _items(
        ("TSK-B", "TSK-A"),
        ("TSK-C", "TSK-A"),
        ("TSK-D", "TSK-B"),
        ("TSK-D", "TSK-C"),
    )
    r1 = compute_graph_stats(items)
    r2 = compute_graph_stats(items)
    assert r1["critical_path"]["nodes"] == r2["critical_path"]["nodes"]
    assert r1["bottleneck_ids"] == r2["bottleneck_ids"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
