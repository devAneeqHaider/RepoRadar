/**
 * Thin API client for the RepoRadar Django backend (API v1).
 *
 * Base URL resolution:
 *   - If import.meta.env.VITE_API_URL is set, it is used as the base
 *     (e.g. "https://api.example.com" -> "https://api.example.com/api/...").
 *   - Otherwise relative "/api/..." paths are used, which the Vite dev
 *     server proxies to http://localhost:8000 (see vite.config.js).
 */

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function url(path) {
  return `${API_BASE}${path}`;
}

async function parseBody(res) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Minimal fetch wrapper: JSON in, JSON out.
 * Throws an Error carrying the server-provided message when available.
 */
async function request(method, path, body) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  const res = await fetch(url(path), options);
  const data = await parseBody(res);

  if (!res.ok) {
    const message =
      (data && typeof data === "object" && (data.error || data.message || data.detail)) ||
      (typeof data === "string" && data) ||
      `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return data;
}

/** POST /api/analyze/ -> { job_id } */
export function analyzeRepo(repoUrl) {
  return request("POST", "/api/analyze/", { repo_url: repoUrl });
}

/** GET /api/jobs/<uuid>/ -> job status payload */
export function getJob(jobId) {
  return request("GET", `/api/jobs/${encodeURIComponent(jobId)}/`);
}

/** GET /api/repos/ -> array of analyzed repos */
export function listRepos() {
  return request("GET", "/api/repos/");
}

/** GET /api/repos/<id>/ -> repo detail + stats */
export function getRepo(id) {
  return request("GET", `/api/repos/${encodeURIComponent(id)}/`);
}

/** GET /api/repos/<id>/graph/ -> { nodes, edges } */
export function getGraph(id) {
  return request("GET", `/api/repos/${encodeURIComponent(id)}/graph/`);
}

/** GET /api/repos/<id>/smells/ -> array of code smells */
export function getSmells(id) {
  return request("GET", `/api/repos/${encodeURIComponent(id)}/smells/`);
}

/** GET /api/repos/<id>/guide/ -> { markdown } */
export function getGuide(id) {
  return request("GET", `/api/repos/${encodeURIComponent(id)}/guide/`);
}

/** GET /api/repos/<id>/report/ -> download the repository analysis PDF */
export async function downloadReport(id) {
  const res = await fetch(url(`/api/repos/${encodeURIComponent(id)}/report/`));
  if (!res.ok) {
    const data = await parseBody(res);
    const message =
      (data && typeof data === "object" && (data.error || data.message || data.detail)) ||
      (typeof data === "string" && data) ||
      `Request failed with status ${res.status}`;
    throw new Error(message);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1]
    || `reporadar-report-${id}.pdf`;
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
