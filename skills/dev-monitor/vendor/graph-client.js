// graph-client.js — Dependency Graph 클라이언트 (TSK-03-04)
// cytoscape + dagre LR, 2초 폴링, diff delta. IIFE. ES2020. ≤300 LOC.
(function () {
  "use strict";

  // -- 상수 --
  const POLL_MS = 2000;
  const COLOR = {
    done:          "#22c55e",
    running:       "#eab308",
    pending:       "#94a3b8",
    failed:        "#ef4444",
    bypassed:      "#a855f7",
    edge_default:  "#475569",
    edge_critical: "#ef4444",
  };

  // -- 상태 --
  let cy = null;
  let SP = "all";
  let lastSignature = "";
  let popoverNodeId = null;
  let _popoverEl = null;

  // -- 노드 스타일 --
  function nodeStyle(node) {
    const color = node.bypassed ? COLOR.bypassed
                : node.status === "[xx]" ? COLOR.done
                : (node.status === "[im]" || node.status === "[ts]") ? COLOR.running
                : node.status === "[dd]" ? COLOR.running
                : (node.status === "failed" || node.status === "[fail]") ? COLOR.failed
                : COLOR.pending;
    const isCrit = node.is_critical;
    return {
      color,
      borderColor: isCrit ? COLOR.edge_critical : color,
      borderWidth: isCrit ? 2 : 0,
      label: (node.is_bottleneck ? "⚠ " : "") + (node.label || node.id),
    };
  }

  // -- delta 적용 --
  function applyDelta(data) {
    const nodes = data.nodes || [];
    const edges = data.edges || [];

    const curNodeIds = new Set(cy.nodes().map(n => n.id()));
    const curEdgeIds = new Set(cy.edges().map(e => e.id()));
    const newNodeIds = new Set(nodes.map(n => n.id));
    const newEdgeIds = new Set(edges.map(e => e.id || `${e.source}__${e.target}`));

    let topoChanged = false;

    // 삭제
    cy.nodes().forEach(n => {
      if (!newNodeIds.has(n.id())) { cy.remove(n); topoChanged = true; }
    });
    cy.edges().forEach(e => {
      if (!newEdgeIds.has(e.id())) { cy.remove(e); topoChanged = true; }
    });

    cy.batch(() => {
      // 노드 추가/갱신
      nodes.forEach(nd => {
        const style = nodeStyle(nd);
        if (!curNodeIds.has(nd.id)) {
          cy.add({ group: "nodes", data: {
            id: nd.id, label: style.label,
            color: style.color, borderWidth: style.borderWidth,
            borderColor: style.borderColor,
            status: nd.status, is_critical: nd.is_critical,
            is_bottleneck: nd.is_bottleneck,
            fan_in: nd.fan_in, fan_out: nd.fan_out,
            bypassed: nd.bypassed, wp_id: nd.wp_id,
            _raw: nd,
          }});
          topoChanged = true;
        } else {
          const ele = cy.getElementById(nd.id);
          ele.data("color", style.color);
          ele.data("borderWidth", style.borderWidth);
          ele.data("borderColor", style.borderColor);
          ele.data("label", style.label);
          ele.data("status", nd.status);
          ele.data("is_critical", nd.is_critical);
          ele.data("is_bottleneck", nd.is_bottleneck);
          ele.data("_raw", nd);
          ele.toggleClass("bottleneck", !!nd.is_bottleneck);
        }
      });

      // 엣지 추가
      edges.forEach(ed => {
        const eid = ed.id || `${ed.source}__${ed.target}`;
        if (!curEdgeIds.has(eid)) {
          cy.add({ group: "edges", data: {
            id: eid, source: ed.source, target: ed.target,
            color: ed.is_critical ? COLOR.edge_critical : COLOR.edge_default,
            width: ed.is_critical ? 3 : 1,
            is_critical: ed.is_critical,
          }});
          topoChanged = true;
        }
      });
    });

    if (topoChanged) {
      cy.layout({ name: "dagre", rankDir: "LR", nodeSep: 40, rankSep: 80 }).run();
    }

    if (popoverNodeId) {
      const ele = cy.getElementById(popoverNodeId);
      if (ele.length) renderPopover(ele);
    }
  }

  // -- 요약 갱신 --
  function getStat(stats, ...keys) {
    for (const k of keys) {
      if (stats[k] != null) return stats[k];
    }
    return "-";
  }

  function updateSummary(stats) {
    if (!stats) return;
    const el = document.getElementById("dep-graph-summary");
    if (!el) return;
    ["total", "done", "running", "pending", "failed", "bypassed"].forEach(k => {
      const span = el.querySelector(`[data-stat="${k}"]`);
      if (span) span.textContent = getStat(stats, k);
    });
    const depth = getStat(stats, "critical_path_depth", "critical_depth");
    const bottleneck = getStat(stats, "bottleneck_count");
    let extra = el.querySelector(".dep-graph-summary-extra");
    if (!extra) {
      extra = document.createElement("span");
      extra.className = "dep-graph-summary-extra";
      el.appendChild(extra);
    }
    extra.textContent = ` | 크리티컬 패스 깊이 ${depth} | 병목 Task ${bottleneck}개`;
  }

  // -- 팝오버 --
  function ensurePopover() {
    if (!_popoverEl) {
      _popoverEl = document.createElement("div");
      _popoverEl.id = "dep-graph-popover";
      _popoverEl.style.cssText = (
        "position:absolute;z-index:100;background:#1e2330;border:1px solid #334155;"
        + "border-radius:6px;padding:10px 14px;font-size:12px;color:#e2e8f0;"
        + "max-width:280px;pointer-events:none;display:none;line-height:1.5;"
      );
      document.body.appendChild(_popoverEl);
    }
    return _popoverEl;
  }

  function renderPopover(ele) {
    const raw = ele.data("_raw") || {};
    const pop = ensurePopover();
    const hist = (raw.phase_history || []).slice(-3).reverse()
      .map(h => `${h.event}: ${h.from_status || "?"}→${h.to_status || "?"}`)
      .join("<br>");
    pop.innerHTML = (
      "<strong>" + (ele.data("label") || ele.id()) + "</strong><br>"
      + "status: " + (raw.status || "-") + "<br>"
      + "depends: " + ((raw.depends || []).join(", ") || "-") + "<br>"
      + (hist ? "<br><em>history:</em><br>" + hist : "")
    );
    const pos = ele.renderedPosition();
    const canvas = document.getElementById("dep-graph-canvas");
    const rect = canvas ? canvas.getBoundingClientRect() : { left: 0, top: 0 };
    pop.style.left = (rect.left + pos.x + 12) + "px";
    pop.style.top  = (rect.top + pos.y + window.scrollY - 10) + "px";
    pop.style.display = "block";
  }

  function hidePopover() {
    popoverNodeId = null;
    if (_popoverEl) _popoverEl.style.display = "none";
  }

  // -- 폴링 --
  async function tick() {
    try {
      const res = await fetch(`/api/graph?subproject=${encodeURIComponent(SP)}`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const sig = data.generated_at || "";
      if (sig && sig === lastSignature) return;
      lastSignature = sig;
      applyDelta(data);
      updateSummary(data.stats);
    } catch (_) { /* silent skip */ }
  }

  // -- 초기화 --
  function init() {
    const section = document.querySelector("section[data-section='dep-graph']");
    if (section) {
      const sp = section.getAttribute("data-subproject");
      if (sp) {
        SP = sp;
      } else {
        const qs = new URLSearchParams(location.search).get("subproject");
        if (qs) SP = qs;
      }
    }

    const container = document.getElementById("dep-graph-canvas");
    if (!container) return;

    cy = cytoscape({
      container,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            "label": "data(label)",
            "font-size": "11px",
            "color": "#e2e8f0",
            "text-valign": "center",
            "text-halign": "center",
            "width": "label",
            "height": "label",
            "padding": "6px",
            "shape": "roundrectangle",
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "transition-property": "background-color border-color",
            "transition-duration": "400ms",
          },
        },
        {
          selector: "edge",
          style: {
            "width": "data(width)",
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
        {
          selector: ".bottleneck",
          style: { "border-style": "dashed", "border-width": 2 },
        },
      ],
      layout: { name: "dagre", rankDir: "LR", nodeSep: 40, rankSep: 80 },
    });

    cy.on("tap", "node", evt => {
      const ele = evt.target;
      popoverNodeId = ele.id();
      renderPopover(ele);
    });
    cy.on("tap", evt => {
      if (evt.target === cy) hidePopover();
    });
    cy.on("pan zoom", () => {
      if (popoverNodeId) {
        const ele = cy.getElementById(popoverNodeId);
        if (ele.length) renderPopover(ele);
      }
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") hidePopover(); });
    document.addEventListener("click", e => {
      if (_popoverEl && !_popoverEl.contains(e.target)) hidePopover();
    });

    tick();
    setInterval(tick, POLL_MS);
  }

  // -- DOM 준비 후 기동 --
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
