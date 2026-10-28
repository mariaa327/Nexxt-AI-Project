"""Application-level service errors.

Each subclass carries a safe ``public_message`` and an ``http_status``. A
handler registered in ``app.main`` turns them into JSON responses, so endpoints
never translate errors themselves and provider details never reach clients.
"""

from __future__ import annotations


class AgentServiceError(RuntimeError):
    """Base class for errors that the API layer turns into HTTP responses."""

    http_status = 502
    public_message = "The AI service failed to produce a response."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class AgentConfigurationError(AgentServiceError):
    """The AI provider is not configured on the server."""

    http_status = 503
    public_message = (
        "The AI service is not configured. Set OPENAI_API_KEY on the backend."
    )


class AgentProviderError(AgentServiceError):
    """The provider rejected the request or could not be reached."""

    http_status = 502
    public_message = "The AI service could not complete the request. Please try again."


class AgentRefusalError(AgentServiceError):
    """The model refused to answer the prompt."""

    http_status = 422
    public_message = "The AI model declined to answer this prompt."


class AgentEmptyResponseError(AgentServiceError):
    """The provider returned no parsed structured output."""

    http_status = 502
    public_message = "The AI service returned an empty response."


class BankingDataError(AgentServiceError):
    """The client data file is missing or malformed."""

    http_status = 500
    public_message = "The client data could not be loaded."


class OptionNotAvailableError(AgentServiceError):
    """The requested option is not offered for the current situation."""

    http_status = 422
    public_message = "That option is not available for the current situation."
