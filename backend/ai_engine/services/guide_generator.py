"""Onboarding-guide generation with a factual static fallback.

``build_guide`` tries Gemini first; on ``AIUnavailableError``/``AIError``
(never configured, network down, bad key, empty answer) it returns a
fully factual fallback guide instead — the pipeline never crashes.
"""
import logging

from ai_engine.services.exceptions import AIError, AIUnavailableError
from ai_engine.services.gemini_client import GeminiProvider
from ai_engine.services.prompts import AI_UNAVAILABLE_NOTE, build_guide_prompt

logger = logging.getLogger(__name__)

README_EXCERPT_CHARS = 3000


def build_guide(
    repo,
    stats: dict,
    top_modules: list[dict],
    entry_points: list[str],
    readme_excerpt: str,
) -> str:
    """Return the onboarding guide Markdown for a repository.

    ``repo`` is a ``repositories.Repository`` instance; ``stats`` the stats
    dict saved on it; ``top_modules``/``entry_points`` plain lists.
    """
    top_languages = stats.get("top_languages", {}) or {}
    tech_stack = ", ".join(
        f"{lang} ({count} files)" for lang, count in list(top_languages.items())[:6]
    ) or "unknown"
    structure_overview = stats.get("structure_overview", "") or "(not computed)"

    try:
        prompt = build_guide_prompt(
            owner=repo.owner,
            name=repo.name,
            description=repo.description or "",
            language=repo.language or "",
            stars=repo.stars or 0,
            file_count=stats.get("file_count", 0),
            module_count=stats.get("module_count", 0),
            class_count=stats.get("class_count", 0),
            function_count=stats.get("function_count", 0),
            tech_stack=tech_stack,
            structure_overview=structure_overview,
            top_modules=top_modules,
            entry_points=entry_points,
            readme_excerpt=(readme_excerpt or "")[:README_EXCERPT_CHARS],
        )
        text = GeminiProvider().generate(prompt)
        if not text.strip():
            raise AIError("Gemini returned an empty guide")
        return text.strip()
    except (AIUnavailableError, AIError) as exc:
        logger.info("Falling back to static guide for %s: %s", repo, exc)
        return _fallback_guide(repo, stats, top_modules, entry_points, tech_stack)


def _fallback_guide(
    repo,
    stats: dict,
    top_modules: list[dict],
    entry_points: list[str],
    tech_stack: str,
) -> str:
    """Deterministic factual guide used when the LLM is unavailable."""
    lines = [
        f"# {repo.owner}/{repo.name} — Onboarding Guide",
        "",
        AI_UNAVAILABLE_NOTE,
        "",
        "## Overview",
        "",
        (repo.description or "No description provided on GitHub.")
        + f" Source: {repo.url}",
        "",
        "## Tech Stack",
        "",
        f"- Primary language: {repo.language or 'unknown'}",
        f"- Languages by file count: {tech_stack}",
        f"- Scale: {stats.get('file_count', 0)} files, "
        f"{stats.get('module_count', 0)} Python modules, "
        f"{stats.get('class_count', 0)} classes, "
        f"{stats.get('function_count', 0)} functions",
        "",
        "## Project Structure",
        "",
        stats.get("structure_overview")
        or "Top-level directories are listed in the dependency graph view.",
        "",
        "## Key Modules",
        "",
    ]
    if top_modules:
        for mod in top_modules:
            lines.append(
                f"- `{mod['path']}` — {mod['classes']} classes, "
                f"{mod['functions']} functions"
            )
    else:
        lines.append("No Python modules were detected in this repository.")
    lines += ["", "## How to Run", ""]
    lines.append(_how_to_run(repo))
    lines += ["", "## Entry Points", ""]
    if entry_points:
        lines.extend(f"- `{p}`" for p in entry_points)
    else:
        lines.append("No conventional entry points (e.g. `main.py`, `manage.py`) "
                     "were detected — check the README for run instructions.")
    lines += [
        "",
        "## Suggested First Contributions",
        "",
        "- Pick a `low`-severity code smell from the Smells tab and fix it — "
        "they are safe, well-scoped first issues.",
        "- Add or improve docstrings in the largest modules listed above.",
        "- If the README is missing setup steps, document the ones you discover "
        "while getting the project running.",
        "",
    ]
    return "\n".join(lines)


def _how_to_run(repo) -> str:
    language = (repo.language or "").lower()
    clone = (
        "1. Clone the repository: `git clone "
        f"{repo.url}.git`\n"
        "2. Read the README for project-specific prerequisites."
    )
    if language == "python":
        return (
            clone
            + "\n3. Create a virtual environment: `python -m venv .venv && "
            "source .venv/bin/activate`\n"
            "4. Install dependencies if declared: "
            "`pip install -r requirements.txt` (or check `pyproject.toml`)."
        )
    if language in ("javascript", "typescript"):
        return (
            clone
            + "\n3. Install dependencies: `npm install`\n"
            "4. Look for `scripts` in `package.json` for dev/build/test commands."
        )
    return clone + "\n3. Follow the language-specific setup in the README."
