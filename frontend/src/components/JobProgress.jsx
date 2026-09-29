import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getJob } from "../api/client.js";

const STAGE_LABELS = {
  pending: "Queued…",
  downloading: "Downloading repository…",
  parsing: "Parsing source files…",
  analyzing: "Analyzing architecture…",
  ai: "Generating AI guide…",
  done: "Done",
  failed: "Failed",
};

// Ordered pipeline stages shown as a stepper
const PIPELINE = ["pending", "downloading", "parsing", "analyzing", "ai", "done"];

export default function JobProgress({ jobId }) {
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const timerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await getJob(jobId);
        if (cancelled) return;
        setJob(data);
        setError("");

        if (data.status === "done") {
          clearInterval(timerRef.current);
          if (data.repository_id) {
            navigate(`/repo/${data.repository_id}`);
          }
        } else if (data.status === "failed") {
          clearInterval(timerRef.current);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err.message || "Could not reach the analysis service.");
        clearInterval(timerRef.current);
      }
    }

    poll();
    timerRef.current = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  if (error && !job) {
    return (
      <div className="job-progress">
        <div className="error-panel">
          <span className="error-icon" aria-hidden="true">⚠</span>
          <h3>Could not track this job</h3>
          <p>{error}</p>
          <Link to="/" className="btn btn-primary">
            Try another repository
          </Link>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="job-progress">
        <div className="loading-state">
          <span className="spinner dark" aria-hidden="true" />
          <p style={{ marginTop: "1rem" }}>Connecting to the analysis service…</p>
        </div>
      </div>
    );
  }

  if (job.status === "failed") {
    return (
      <div className="job-progress">
        <div className="error-panel">
          <span className="error-icon" aria-hidden="true">✕</span>
          <h3>Analysis failed</h3>
          <p>{job.error || "The repository could not be analyzed."}</p>
          <Link to="/" className="btn btn-primary">
            Try another repository
          </Link>
        </div>
      </div>
    );
  }

  const progress = Math.max(0, Math.min(100, job.progress ?? 0));
  const currentIndex = PIPELINE.indexOf(job.status);

  return (
    <div className="job-progress">
      <h2>Analyzing repository</h2>
      <p className="stage-label">{STAGE_LABELS[job.status] || job.status}</p>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={Math.round(progress)}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label={STAGE_LABELS[job.status] || job.status}
      >
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p className="progress-pct">{Math.round(progress)}%</p>
      {job.message && <p className="server-message">{job.message}</p>}
      <div className="stage-steps" aria-hidden="true">
        {PIPELINE.slice(0, -1).map((stage, i) => (
          <span
            key={stage}
            className={
              "stage-step" +
              (i === currentIndex ? " active" : "") +
              (i < currentIndex ? " finished" : "")
            }
          >
            {STAGE_LABELS[stage].replace("…", "")}
          </span>
        ))}
      </div>
    </div>
  );
}
