"""Errors of the agent steps that the API layer maps to HTTP responses."""


class InvalidInputError(ValueError):
    """Input that passes the contract schema but not the knowledge base (HTTP 400).
    `message` is German and safe to show to the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
