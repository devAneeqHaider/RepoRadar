import { useEffect, useMemo, useState } from "react";
import { getSmells } from "../api/client.js";

const FILTERS = ["all", "high", "medium", "low"];

function SmellRow({ smell }) {
  const [open, setOpen] = useState(false);
  const severity = (smell.severity || "low").toLowerCase();
  const location = [smell.file, smell.line !== undefined && smell.line !== null ? `:${smell.line}` : ""]
    .filter(Boolean)
    .join("");

  return (
    <div className={`smell-row${open ? " open" : ""}`}>
      <button
        className="smell-row-header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`badge sev-${severity}`}>
          {severity.charAt(0).toUpperCase() + severity.slice(1)}
        </span>
        <span className="smell-row-title">{smell.title || "Code smell"}</span>
        {location && <span className="smell-row-file">{location}</span>}
        <span className="smell-row-chevron" aria-hidden="true">
          ▼
        </span>
      </button>
      {open && (
        <div className="smell-row-body">
          {location && (
            <div className="smell-section">
              <div className="smell-section-title">Location</div>
              <code>{location}</code>
              {smell.type && <span style={{ marginLeft: "0.6rem" }}>· {smell.type}</span>}
            </div>
          )}
          {smell.detail && (
            <div className="smell-section">
              <div className="smell-section-title">Detail</div>
              <p>{smell.detail}</p>
            </div>
          )}
          {smell.explanation && (
            <div className="smell-section">
              <div className="smell-section-title">Why it matters</div>
              <p>{smell.explanation}</p>
            </div>
          )}
          {smell.suggestion && (
            <div className="smell-section">
              <div className="smell-section-title">Suggestion</div>
              <p>{smell.suggestion}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SmellList({ repoId }) {
  const [smells, setSmells] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getSmells(repoId);
        if (cancelled) return;
        setSmells(Array.isArray(data) ? data : []);
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Failed to load code smells.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  const counts = useMemo(() => {
    const c = { all: smells.length, high: 0, medium: 0, low: 0 };
    for (const s of smells) {
      const sev = (s.severity || "low").toLowerCase();
      if (c[sev] !== undefined) c[sev] += 1;
    }
    return c;
  }, [smells]);

  const visible = useMemo(
    () =>
      filter === "all"
        ? smells
        : smells.filter(
            (s) => (s.severity || "low").toLowerCase() === filter,
          ),
    [smells, filter],
  );

  if (loading) {
    return (
      <div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="skeleton"
            style={{ height: "64px", marginBottom: "0.75rem" }}
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-panel">
        <span className="error-icon" aria-hidden="true">⚠</span>
        <h3>Could not load code smells</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (smells.length === 0) {
    return (
      <div className="empty-state card">
        <span className="empty-icon" aria-hidden="true">✨</span>
        <h3>No code smells detected</h3>
        <p>This repository came back clean. Nice work.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="smell-filters" role="group" aria-label="Filter by severity">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={`smell-filter${filter === f ? " active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
            <span className="filter-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <div className="empty-state">
          <p>No {filter}-severity smells found.</p>
        </div>
      ) : (
        <div className="smell-list">
          {visible.map((smell) => (
            <SmellRow key={smell.id || `${smell.title}-${smell.file}-${smell.line}`} smell={smell} />
          ))}
        </div>
      )}
    </div>
  );
}
