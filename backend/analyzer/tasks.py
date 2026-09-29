"""Background analysis pipeline: download -> parse -> analyze -> AI -> done.

Every stage updates the ``AnalysisJob`` row so the frontend can poll
``GET /api/jobs/<uuid>/``. The whole body is wrapped in try/except so a
failure always lands the job in ``failed`` with a message, and the temp
directory is always cleaned up.
"""
import logging
import os
import shutil

from celery import shared_task
from django.utils import timezone

from ai_engine.services.guide_generator import build_guide
from ai_engine.services.smell_explainer import explain_smells
from analyzer.services.github_client import GithubClient
from analyzer.services.graph_builder import build_graph
from analyzer.services.python_parser import parse_python_files
from analyzer.services.smell_detector import detect_smells
from analyzer.services.walker import walk_tree
from repositories.models import AnalysisJob

logger = logging.getLogger(__name__)

ENTRY_POINT_BASENAMES = {
    "main.py",
    "app.py",
    "manage.py",
    "run.py",
    "cli.py",
    "wsgi.py",
    "asgi.py",
}
README_BASENAMES = {"readme.md", "readme.rst", "readme.txt"}
TOP_MODULE_LIMIT = 8


def _set_stage(job: AnalysisJob, status: str, progress: int, message: str) -> None:
    job.status = status
    job.progress = progress
    job.message = message
    job.save(update_fields=["status", "progress", "message", "updated_at"])


def _top_level_overview(files: list[dict]) -> str:
    top_dirs: set[str] = set()
    top_files: list[str] = []
    for entry in files:
        parts = entry["path"].split("/")
        if len(parts) > 1:
            top_dirs.add(parts[0])
        else:
            top_files.append(parts[0])
    bits = [f"directories: {', '.join(sorted(top_dirs))}" if top_dirs else ""]
    if top_files:
        bits.append(f"top-level files: {', '.join(sorted(top_files)[:10])}")
    return "; ".join(b for b in bits if b) or "flat layout"


def _top_modules(parsed: dict) -> list[dict]:
    modules = parsed.get("modules", {})
    ranked = sorted(
        modules.items(),
        key=lambda kv: (len(kv[1]["classes"]) + len(kv[1]["functions"]), kv[1]["loc"]),
        reverse=True,
    )
    return [
        {
            "name": dotted or info["path"],
            "path": info["path"],
            "classes": len(info["classes"]),
            "functions": len(info["functions"]),
        }
        for dotted, info in ranked[:TOP_MODULE_LIMIT]
    ]


def _entry_points(files: list[dict]) -> list[str]:
    found = []
    for entry in files:
        base = entry["path"].split("/")[-1]
        if base in ENTRY_POINT_BASENAMES or entry["path"].endswith("/__main__.py"):
            found.append(entry["path"])
    return sorted(found)[:10]


def _readme_excerpt(root: str, files: list[dict], limit: int = 3000) -> str:
    for entry in files:
        if entry["path"].split("/")[-1].lower() in README_BASENAMES:
            try:
                with open(
                    os.path.join(root, entry["path"]),
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as fh:
                    return fh.read(limit)
            except OSError:
                return ""
    return ""


@shared_task(bind=True, name="analyzer.run_analysis")
def run_analysis(self, job_id: str) -> None:
    job = AnalysisJob.objects.select_related("repository").get(id=job_id)
    repo = job.repository
    tmp_dir: str | None = None
    try:
        owner, name = repo.owner, repo.name
        client = GithubClient()

        # 1. downloading (5-20)
        _set_stage(job, "downloading", 5, f"Preparing download of {owner}/{name}…")
        _set_stage(job, "downloading", 10, f"Downloading {owner}/{name} tarball…")
        tmp_dir, dl_meta = client.download(owner, name)
        repo.default_branch = dl_meta.get("default_branch", "main")
        meta = client.fetch_repo_meta(owner, name)  # best effort, never raises
        if meta:
            repo.stars = meta.get("stars", 0)
            repo.description = meta.get("description") or ""
            repo.language = meta.get("language") or ""
        repo.save(
            update_fields=["default_branch", "stars", "description", "language", "updated_at"]
        )
        _set_stage(job, "downloading", 20, "Download complete.")

        # 2. parsing (20-45)
        _set_stage(job, "parsing", 25, "Walking file tree…")
        files, top_languages = walk_tree(tmp_dir)
        n_python = sum(1 for f in files if f["language"] == "Python")
        _set_stage(job, "parsing", 35, f"Parsing {n_python} Python files…")
        parsed = parse_python_files(tmp_dir, files)
        if parsed["unparsed_files"]:
            logger.info(
                "Skipped %d unparseable files", len(parsed["unparsed_files"])
            )
        _set_stage(job, "parsing", 45, "Parsing complete.")

        # 3. analyzing (45-70)
        _set_stage(job, "analyzing", 55, "Building dependency graph…")
        graph = build_graph(parsed)
        _set_stage(job, "analyzing", 62, "Detecting code smells…")
        smells = detect_smells(parsed, graph)
        stats = {
            "file_count": len(files),
            "module_count": parsed["module_count"],
            "class_count": parsed["class_count"],
            "function_count": parsed["function_count"],
            "top_languages": top_languages,
            "structure_overview": _top_level_overview(files),
            "unparsed_files": len(parsed["unparsed_files"]),
        }
        repo.stats = stats
        repo.graph_data = graph
        repo.smells = smells
        repo.save(update_fields=["stats", "graph_data", "smells", "updated_at"])
        _set_stage(job, "analyzing", 70, "Static analysis complete.")

        # 4. ai (70-92) — failures degrade to static fallbacks, job continues
        _set_stage(job, "ai", 75, "Generating onboarding guide…")
        guide = build_guide(
            repo,
            stats,
            _top_modules(parsed),
            _entry_points(files),
            _readme_excerpt(tmp_dir, files),
        )
        _set_stage(job, "ai", 85, "Explaining code smells…")
        smells = explain_smells(smells)
        repo.guide_markdown = guide
        repo.smells = smells
        repo.save(update_fields=["guide_markdown", "smells", "updated_at"])
        _set_stage(job, "ai", 92, "AI enrichment complete.")

        # 5. done (100)
        repo.analyzed_at = timezone.now()
        repo.save(update_fields=["analyzed_at", "updated_at"])
        _set_stage(job, "done", 100, "Analysis complete.")
    except Exception as exc:  # noqa: BLE001 - surfaced on the job row
        logger.exception("Analysis job %s failed", job_id)
        job.status = "failed"
        job.error = str(exc)[:2000]
        job.message = "Analysis failed."
        job.save(update_fields=["status", "error", "message", "updated_at"])
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
