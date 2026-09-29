"""AI engine exceptions."""


class AIError(Exception):
    """Base class for recoverable AI provider failures (transport, API, shape)."""


class AIUnavailableError(AIError):
    """Raised when no AI provider is configured (e.g. GEMINI_API_KEY missing)."""
