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
        "The AI service is not configured. Set the AWS credentials on the backend."
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


class ChallengeNotFoundError(AgentServiceError):
    """No verification request with that id (or the demo was reset)."""

    http_status = 404
    public_message = "Verification request not found. Start the payment again."


class ChallengeNotApprovedError(AgentServiceError):
    """The verification is still pending, was cancelled, or was already used."""

    http_status = 409
    public_message = "The payment has not been approved in the banking app."


class ChallengeExpiredError(AgentServiceError):
    """The verification request timed out."""

    http_status = 410
    public_message = "The verification request expired. Start the payment again."


class NotAuthenticatedError(AgentServiceError):
    """Missing, invalid or expired session token."""

    http_status = 401
    public_message = "Please log in again."


class InvalidCredentialsError(AgentServiceError):
    """Wrong username or password; deliberately does not say which."""

    http_status = 401
    public_message = "Incorrect username or password."


class DatabaseUnavailableError(AgentServiceError):
    http_status = 503
    public_message = "The bank database is unavailable. Is PostgreSQL running?"


class InvalidClientDataError(AgentServiceError):
    """Client data does not match the expected format."""

    http_status = 422
    public_message = "The client data is not in the expected format."

    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason)
        if reason:
            # The reason names fields of the data file, never server internals.
            self.public_message = f"Invalid client data: {reason}"
