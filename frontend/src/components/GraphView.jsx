import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { getGraph } from "../api/client.js";

const NODE_COLORS = {
  module: "#637bc0", // soft blue
  class: "#49a581", // mint green
};
const DEFAULT_NODE_COLOR = "#2a9eb6";

function nodeColor(node) {
  return NODE_COLORS[node.type] || DEFAULT_NODE_COLOR;
}

export default function GraphView({ repoId }) {
  const containerRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 560 });
  // Held in a ref so the canvas painter always sees the latest selection
  const selectedRef = useRef(null);
  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const graph = await getGraph(repoId);
        if (cancelled) return;
        setData(graph);
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Failed to load the architecture graph.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  // Keep the canvas sized to its container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect;
      setDimensions({
        width: Math.max(320, rect.width),
        height: Math.max(420, rect.height || 560),
      });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const nodes = (data.nodes || []).map((n) => ({
      ...n,
      // react-force-graph resolves links by these fields; keep original too
      color: nodeColor(n),
    }));
    const links = (data.edges || []).map((e) => ({
      source: e.from,
      target: e.to,
      type: e.type,
    }));
    return { nodes, links };
  }, [data]);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const radius = node.type === "class" ? 7 : 9;
    const color = nodeColor(node);

    // Glow
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
    ctx.fillStyle =
      node === selectedRef.current
        ? "rgba(84,119,189,0.25)"
        : `${color}33`;
    ctx.fill();

    // Node body
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Label
    const label = node.label || node.id;
    const fontSize = 12 / globalScale;
    ctx.font = `600 ${fontSize}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(39,52,77,0.92)";
    ctx.fillText(label, node.x, node.y + radius + 4);
  }, []);

  if (loading) {
    return (
      <div className="graph-layout">
        <div className="graph-canvas-wrap">
          <div className="loading-state">
            <span className="spinner dark" aria-hidden="true" />
            <p style={{ marginTop: "1rem" }}>Loading architecture graph…</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-panel">
        <span className="error-icon" aria-hidden="true">⚠</span>
        <h3>Could not load the graph</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <div className="empty-state card">
        <span className="empty-icon" aria-hidden="true">🕸</span>
        <h3>No graph data</h3>
        <p>
          This repository did not produce any module or class relationships to
          visualize.
        </p>
      </div>
    );
  }

  return (
    <div className="graph-layout">
      <div className="graph-canvas-wrap" ref={containerRef}>
        <div className="graph-legend">
          <span className="badge">
            <span className="dot" style={{ background: NODE_COLORS.module }} />
            Module
          </span>
          <span className="badge">
            <span className="dot" style={{ background: NODE_COLORS.class }} />
            Class
          </span>
        </div>
        <ForceGraph2D
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="rgba(0,0,0,0)"
          nodeCanvasObject={paintNode}
          nodeLabel={(node) => `${node.label || node.id} (${node.type || "node"})`}
          linkColor={() => "rgba(104,122,156,0.38)"}
          linkWidth={1.2}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          onNodeClick={(node) => setSelected(node)}
          onBackgroundClick={() => setSelected(null)}
          cooldownTicks={80}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.35}
        />
      </div>
      <aside className="graph-side">
        {selected ? (
          <>
            <h3>Node details</h3>
            <p className="node-label">{selected.label || selected.id}</p>
            <span
              className="badge"
              style={{ color: nodeColor(selected), borderColor: `${nodeColor(selected)}66` }}
            >
              <span className="dot" style={{ background: nodeColor(selected) }} />
              {selected.type || "node"}
            </span>
            <dl>
              {selected.path && (
                <>
                  <dt>Path</dt>
                  <dd>{selected.path}</dd>
                </>
              )}
              <dt>ID</dt>
              <dd>{selected.id}</dd>
            </dl>
          </>
        ) : (
          <>
            <h3>Architecture graph</h3>
            <p className="side-hint">
              {data.nodes.length} nodes · {data.edges?.length || 0} import edges.
              Click a node to inspect its module, class, and file path.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
