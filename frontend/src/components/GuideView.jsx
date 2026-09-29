import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getGuide } from "../api/client.js";

export default function GuideView({ repoId }) {
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getGuide(repoId);
        if (cancelled) return;
        setMarkdown(data && data.markdown ? data.markdown : "");
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Failed to load the onboarding guide.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  if (loading) {
    return (
      <div>
        <div className="skeleton" style={{ height: "32px", width: "40%", marginBottom: "1rem" }} />
        <div className="skeleton" style={{ height: "16px", marginBottom: "0.6rem" }} />
        <div className="skeleton" style={{ height: "16px", width: "85%", marginBottom: "0.6rem" }} />
        <div className="skeleton" style={{ height: "16px", width: "70%", marginBottom: "1.5rem" }} />
        <div className="skeleton" style={{ height: "28px", width: "30%", marginBottom: "1rem" }} />
        <div className="skeleton" style={{ height: "16px", marginBottom: "0.6rem" }} />
        <div className="skeleton" style={{ height: "16px", width: "90%" }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-panel">
        <span className="error-icon" aria-hidden="true">⚠</span>
        <h3>Could not load the onboarding guide</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!markdown) {
    return (
      <div className="empty-state card">
        <span className="empty-icon" aria-hidden="true">📖</span>
        <h3>No guide available</h3>
        <p>An onboarding guide was not generated for this repository.</p>
      </div>
    );
  }

  return (
    <article className="guide-article">
      <ReactMarkdown>{markdown}</ReactMarkdown>
    </article>
  );
}
