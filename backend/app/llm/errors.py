"""Typed LLM errors. The API layer maps them to HTTP responses in one handler."""


class LLMError(Exception):
    """Base class. `message` is German and safe to show to the user."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class LLMUnavailableError(LLMError):
    """No key or model configured, provider unreachable, timeout or rate limit exhausted."""


class LLMOutputError(LLMError):
    """The output failed validation twice, or was cut off."""


class RefusalError(LLMError):
    """The model refused to answer."""
