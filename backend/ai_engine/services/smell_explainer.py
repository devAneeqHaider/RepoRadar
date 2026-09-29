"""Batch LLM explanations for detected code smells.

The top 10 smells by severity go through ONE Gemini call (JSON in/out).
Any AI failure returns the smell list unchanged — the detector's static
``suggestion`` still stands on its own.
"""
import json
import logging
import re

from ai_engine.services.exceptions import AIError, AIUnavailableError
from ai_engine.services.gemini_client import GeminiProvider
from ai_engine.services.prompts import build_smell_explanation_prompt
from analyzer.services.smell_detector import SEVERITY_RANK

logger = logging.getLogger(__name__)

MAX_EXPLAINED = 10


def explain_smells(smells: list[dict]) -> list[dict]:
    """Add an ``explanation`` key to the worst smells. Never raises for AI issues."""
    if not smells:
        return smells
    ranked = sorted(
        smells,
        key=lambda s: (SEVERITY_RANK.get(s.get("severity"), 99), s.get("id", "")),
    )
    batch = ranked[:MAX_EXPLAINED]
    try:
        raw = GeminiProvider().generate(build_smell_explanation_prompt(batch))
        explanations = _parse_explanations(raw)
    except (AIUnavailableError, AIError) as exc:
        logger.info("Smell explanations skipped (AI unavailable): %s", exc)
        return smells
    for smell in smells:
        text = explanations.get(str(smell.get("id")))
        if text:
            smell["explanation"] = text
    return smells


def _parse_explanations(raw: str) -> dict[str, str]:
    """Extract {id: explanation} from a JSON array, tolerating code fences."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIError(f"Could not parse explanation JSON: {exc}") from exc
    if not isinstance(data, list):
        raise AIError("Explanation response was not a JSON array")
    result: dict[str, str] = {}
    for item in data:
        if isinstance(item, dict) and item.get("id") and item.get("explanation"):
            result[str(item["id"])] = str(item["explanation"]).strip()
    return result
