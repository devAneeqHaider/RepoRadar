import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import RepoForm from "../components/RepoForm.jsx";
import { listRepos } from "../api/client.js";

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function RecentRepos() {
  const [repos, setRepos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await listRepos();
        if (cancelled) return;
        setRepos(Array.isArray(data) ? data : []);
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Failed to load recently analyzed repositories.");
        setRepos([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section aria-label="Recently analyzed repositories">
      <h2 className="section-title">
        Recently analyzed
        {repos && repos.length > 0 && (
          <span className="count">{repos.length}</span>
        )}
      </h2>

      {repos === null && (
        <div className="repo-grid">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="skeleton"
              style={{ height: "150px", borderRadius: "12px" }}
            />
          ))}
        </div>
      )}

      {error && (
        <div className="error-panel">
          <p>{error}</p>
        </div>
      )}

      {repos && repos.length === 0 && !error && (
        <div className="empty-state card">
          <span className="empty-icon" aria-hidden="true">📦</span>
          <h3>No repositories yet</h3>
          <p>Paste a GitHub URL above to run your first analysis.</p>
        </div>
      )}

      {repos && repos.length > 0 && (
        <div className="repo-grid">
          {repos.map((repo) => (
            <Link
              key={repo.id}
              to={`/repo/${repo.id}`}
              className="repo-card"
            >
              <div className="repo-card-title">
                <span className="owner">{repo.owner}/</span>
                {repo.name}
              </div>
              <div className="repo-card-meta">
                {repo.language && (
                  <span className="badge">
                    <span
                      className="dot"
                      style={{ background: "var(--accent-strong)" }}
                    />
                    {repo.language}
                  </span>
                )}
                <span title="GitHub stars">★ {(repo.stars ?? 0).toLocaleString("en-US")}</span>
              </div>
              <div className="analyzed-at">
                Analyzed {formatDate(repo.analyzed_at)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export default function Home() {
  return (
    <div>
      <section className="hero">
        <span className="hero-kicker">AI Repository Architect</span>
        <h1>
          Read Less Code. <span className="gradient-text">Understand More.</span>
        </h1>
        <div className="feature-bullets">
          <span className="badge">🕸 Architecture graph</span>
          <span className="badge">🔍 Code-smell detection</span>
          <span className="badge">🤖 AI onboarding guide</span>
          <span className="badge">🐍 Python-first analysis</span>
        </div>
      </section>

      <RepoForm />
      <RecentRepos />
    </div>
  );
}
