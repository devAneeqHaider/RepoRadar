import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeRepo } from "../api/client.js";

const GITHUB_URL_REGEX = /^https:\/\/github\.com\/[^/]+\/[^/]+\/?$/;

export default function RepoForm() {
  const navigate = useNavigate();
  const [repoUrl, setRepoUrl] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const trimmed = repoUrl.trim();
  const invalid =
    touched && (trimmed === "" || !GITHUB_URL_REGEX.test(trimmed));

  function validate(value) {
    const v = value.trim();
    if (v === "") return "Please enter a GitHub repository URL.";
    if (!GITHUB_URL_REGEX.test(v))
      return "Enter a valid URL like https://github.com/owner/repo";
    return "";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setTouched(true);
    const err = validate(repoUrl);
    if (err) return;

    setSubmitting(true);
    setSubmitError("");
    try {
      const { job_id } = await analyzeRepo(trimmed);
      navigate(`/job/${job_id}`);
    } catch (err2) {
      setSubmitError(err2.message || "Failed to start analysis. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <form className="repo-form" onSubmit={handleSubmit} noValidate>
      <label htmlFor="repo-url">Analyze a repository</label>
      <div className="input-row">
        <input
          id="repo-url"
          type="url"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => {
            setRepoUrl(e.target.value);
            setSubmitError("");
          }}
          onBlur={() => setTouched(true)}
          className={invalid ? "invalid" : ""}
          disabled={submitting}
          autoComplete="off"
          spellCheck="false"
        />
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? (
            <>
              <span className="spinner" aria-hidden="true" /> Starting…
            </>
          ) : (
            "Analyze"
          )}
        </button>
      </div>
      {invalid && (
        <p className="form-error" role="alert">
          ⚠ {validate(repoUrl)}
        </p>
      )}
      <p className="form-hint">
        Public repositories only. Analysis typically takes under a minute.
      </p>
      {submitError && (
        <div className="error-panel form-submit-error">
          <p>{submitError}</p>
        </div>
      )}
    </form>
  );
}
