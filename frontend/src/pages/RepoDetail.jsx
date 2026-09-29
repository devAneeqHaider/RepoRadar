import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import StatCards from "../components/StatCards.jsx";
import GraphView from "../components/GraphView.jsx";
import SmellList from "../components/SmellList.jsx";
import GuideView from "../components/GuideView.jsx";
import { getRepo, getSmells } from "../api/client.js";

const TABS = ["overview", "graph", "smells", "guide"];

const TAB_LABELS = {
  overview: "Overview",
  graph: "Graph",
  smells: "Code Smells",
  guide: "Onboarding Guide",
};

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function LanguageBars({ topLanguages }) {
  const entries = useMemo(() => {
    if (!topLanguages) return [];
    if (Array.isArray(topLanguages)) return topLanguages;
    // Accept an object map: { Python: 72.5, ... }
    return Object.entries(topLanguages).map(([name, value]) => ({
      name,
      pct: value,
    }));
  }, [topLanguages]);

  if (entries.length === 0) return null;

  const total = entries.reduce((sum, e) => sum + (Number(e.pct) || 0), 0);
  const normalized = entries.map((e) => ({
    name: e.name,
    pct: total > 0 ? (Number(e.pct) / total) * 100 : 0,
  }));

  return (
    <div className="lang-bars">
      <h3>Top languages</h3>
      {normalized.map((lang) => (
        <div className="lang-row" key={lang.name}>
          <span className="lang-name">{lang.name}</span>
          <div className="lang-bar-track">
            <div
              className="lang-bar-fill"
              style={{ width: `${Math.max(2, Math.min(100, lang.pct))}%` }}
            />
          </div>
          <span className="lang-pct">{lang.pct.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

function RepoDetailSkeleton() {
  return (
    <div>
      <div className="skeleton" style={{ height: "150px", borderRadius: "12px", marginBottom: "1.5rem" }} />
      <div className="stat-grid">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton" style={{ height: "96px", borderRadius: "12px" }} />
        ))}
      </div>
    </div>
  );
}

export default function RepoDetail() {
  const { id } = useParams();
  const [repo, setRepo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [smellCount, setSmellCount] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getRepo(id);
        if (cancelled) return;
        setRepo(data);
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Failed to load repository details.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Fetch smell count for the tab label (cheap, non-blocking)
  useEffect(() => {
    let cancelled = false;
    async function loadCount() {
      try {
        const data = await getSmells(id);
        if (cancelled) return;
        setSmellCount(Array.isArray(data) ? data.length : 0);
      } catch {
        if (!cancelled) setSmellCount(null);
      }
    }
    loadCount();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <RepoDetailSkeleton />;

  if (error || !repo) {
    return (
      <div className="error-panel" style={{ marginTop: "3rem" }}>
        <span className="error-icon" aria-hidden="true">⚠</span>
        <h3>Repository not found</h3>
        <p>{error || "This repository does not exist or has not been analyzed yet."}</p>
        <Link to="/" className="btn btn-primary">
          Analyze a repository
        </Link>
      </div>
    );
  }

  return (
    <div>
      <header className="repo-header">
        <h1 className="repo-title">
          <span className="owner">{repo.owner}/</span>
          {repo.name}
        </h1>
        {repo.description && (
          <p className="repo-description">{repo.description}</p>
        )}
        <div className="repo-meta">
          {repo.language && <span className="badge">{repo.language}</span>}
          <span className="badge" title="GitHub stars">
            ★ {(repo.stars ?? 0).toLocaleString("en-US")} stars
          </span>
          {repo.url && (
            <a
              href={repo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="github-link"
            >
              View on GitHub ↗
            </a>
          )}
        </div>
        <div className="analyzed-line">
          Analyzed {formatDate(repo.analyzed_at)}
        </div>
      </header>

      <nav className="tabs" role="tablist" aria-label="Repository sections">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`tab${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {TAB_LABELS[t]}
            {t === "smells" && smellCount !== null && (
              <span className="tab-count">{smellCount}</span>
            )}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <div>
          <StatCards stats={repo.stats} stars={repo.stars} language={repo.language} />
          <LanguageBars topLanguages={repo.stats?.top_languages} />
          {repo.description && (
            <div className="card">
              <h3 style={{ marginBottom: "0.6rem", fontSize: "1.05rem" }}>About</h3>
              <p style={{ color: "var(--text-muted)" }}>{repo.description}</p>
            </div>
          )}
        </div>
      )}

      {tab === "graph" && <GraphView repoId={id} />}

      {tab === "smells" && <SmellList repoId={id} />}

      {tab === "guide" && <GuideView repoId={id} />}
    </div>
  );
}
