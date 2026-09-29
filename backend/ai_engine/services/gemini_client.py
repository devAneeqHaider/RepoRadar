"""Google Gemini provider with graceful degradation.

Uses the ``google-generativeai`` package when importable, otherwise falls
back to a plain ``urllib`` REST call against the Generative Language API —
either way the public surface is identical.

The API key is read from the environment at *call* time (never at import),
so key rotation and test fixtures work without restarting the process.
A missing key raises :class:`AIUnavailableError`; every other failure raises
:class:`AIError`. Callers are expected to catch these and degrade to the
static fallbacks — the pipeline must never crash for lack of AI.
"""
import json
import logging
import os
import urllib.request

from ai_engine.services.exceptions import AIError, AIUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash-lite"
_REST_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiProvider:
    """Thin wrapper around Google's Gemini text generation."""

    def __init__(self, model: str | None = None, timeout: int = 60) -> None:
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """Generate text for ``prompt``. Raises AIUnavailableError/AIError."""
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise AIUnavailableError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/ and export it to enable AI features."
            )
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError:
            logger.info("google-generativeai not installed; using REST fallback")
            return self._generate_rest(prompt, api_key)
        return self._generate_sdk(prompt, api_key, genai)

    def _generate_sdk(self, prompt: str, api_key: str, genai) -> str:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(
                prompt, request_options={"timeout": self.timeout}
            )
            text = (getattr(response, "text", "") or "").strip()
        except Exception as exc:  # noqa: BLE001 - wrapped below
            raise AIError(f"Gemini request failed: {exc}") from exc
        if not text:
            raise AIError("Gemini returned an empty response")
        return text

    def _generate_rest(self, prompt: str, api_key: str) -> str:
        url = f"{_REST_ENDPOINT.format(model=self.model)}?key={api_key}"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - wrapped below
            raise AIError(f"Gemini REST request failed: {exc}") from exc
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise AIError(f"Unexpected Gemini response shape: {exc}") from exc
        if not text:
            raise AIError("Gemini returned an empty response")
        return text
