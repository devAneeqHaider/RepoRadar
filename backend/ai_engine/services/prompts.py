"""All LLM prompt strings for RepoRadar live here.

Nothing else in the codebase may contain inline prompt text — build prompts
with the builder functions below so copy stays in one reviewable place.
"""

GUIDE_INTRO = (
    "You are RepoRadar, an expert software architect writing an onboarding "
    "guide for a developer who just joined this open-source project."
)

GUIDE_TASK = (
    "Write a clear, practical onboarding guide in Markdown for the repository "
    "described below. Use exactly these section headings, in this order:\n"
    "## Overview\n"
    "## Tech Stack\n"
    "## Project Structure\n"
    "## Key Modules\n"
    "## How to Run\n"
    "## Entry Points\n"
    "## Suggested First Contributions\n\n"
    "Rules: be concrete and specific to THIS repository — reference real file "
    "paths and module names from the facts given. Keep it under 600 words. "
    "Do not invent files, commands, or dependencies that are not supported "
    "by the facts. If a fact is missing, say so briefly instead of guessing."
)

SMELL_EXPLAINER_INTRO = (
    "You are RepoRadar, a senior code reviewer explaining static-analysis "
    "findings to the maintainers of an open-source repository."
)

SMELL_EXPLAINER_TASK = (
    "For each code smell in the JSON list below, write a one-to-two sentence "
    "plain-English 'explanation' of WHY it matters for this codebase and what "
    "could go wrong if ignored. Respond with a single JSON array — no Markdown "
    "fences, no prose — where each element is "
    '{"id": "<same id>", "explanation": "<your text>"}.'
)

AI_UNAVAILABLE_NOTE = (
    "> AI-generated guide unavailable — set GEMINI_API_KEY to enable richer "
    "guides (free at Google AI Studio)."
)


def build_guide_prompt(
    *,
    owner: str,
    name: str,
    description: str,
    language: str,
    stars: int,
    file_count: int,
    module_count: int,
    class_count: int,
    function_count: int,
    tech_stack: str,
    structure_overview: str,
    top_modules: list[dict],
    entry_points: list[str],
    readme_excerpt: str,
) -> str:
    """Assemble the onboarding-guide prompt from analysis facts."""
    module_lines = "\n".join(
        f"- {m['name']} ({m['path']}) — "
        f"{m['classes']} classes, {m['functions']} functions"
        for m in top_modules
    ) or "- (no Python modules detected)"
    entry_lines = "\n".join(f"- {p}" for p in entry_points) or "- (none detected)"
    facts = (
        f"Repository: {owner}/{name}\n"
        f"Description: {description or '(none provided)'}\n"
        f"Primary language: {language or 'unknown'} | Stars: {stars}\n"
        f"Scale: {file_count} files, {module_count} Python modules, "
        f"{class_count} classes, {function_count} functions\n"
        f"Tech stack (by file count): {tech_stack}\n"
        f"Top-level layout: {structure_overview}\n"
        f"Largest modules:\n{module_lines}\n"
        f"Detected entry points:\n{entry_lines}\n"
        f"README excerpt:\n{readme_excerpt or '(no README found)'}\n"
    )
    return f"{GUIDE_INTRO}\n\n{GUIDE_TASK}\n\nRepository facts:\n{facts}"


def build_smell_explanation_prompt(smells: list[dict]) -> str:
    """Assemble the batched smell-explanation prompt (JSON in, JSON out)."""
    import json

    compact = [
        {
            "id": s["id"],
            "type": s["type"],
            "severity": s["severity"],
            "title": s["title"],
            "file": s["file"],
            "line": s["line"],
            "detail": s["detail"],
        }
        for s in smells
    ]
    return (
        f"{SMELL_EXPLAINER_INTRO}\n\n{SMELL_EXPLAINER_TASK}\n\n"
        f"Code smells:\n{json.dumps(compact, indent=2)}"
    )
