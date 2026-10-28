"""AI agent service built on the native OpenAI Python SDK.

The service owns everything about talking to the model: prompt construction,
the structured-output call and translation of provider failures into
application-level exceptions. Endpoints never see raw SDK errors.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.core.config import settings
from app.schemas.agent import AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a concise, helpful assistant embedded in a hackathon starter app. "
    "Answer the user's question directly, then list the essential key points and "
    "a few useful follow-up questions. If the request is unclear, answer the most "
    "plausible interpretation and note the ambiguity in the answer."
)

# Placeholder for future tool support. Define tool schemas here and dispatch
# their calls in ``AIAgentService.run`` once a tool is actually implemented.
# Nothing below pretends to be functional today.
TOOL_DEFINITIONS: list[dict[str, Any]] = []


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


class AIAgentService:
    """Runs a single prompt through the model and returns validated output."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        # The client is created lazily so importing the app (or running the
        # health check) works without a key.
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise AgentConfigurationError()
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    @staticmethod
    def build_input(prompt: str) -> str:
        """Turn a user prompt into the model input.

        Kept separate from the endpoint so prompt engineering stays in one
        place as the agent grows.
        """
        return (
            "User request:\n"
            f"{prompt.strip()}\n\n"
            "Respond with a direct answer, 3-5 key points and up to 3 follow-up questions."
        )

    def run(self, prompt: str) -> AgentOutput:
        """Call the model with structured output and return a validated result."""
        client = self._get_client()

        request: dict[str, Any] = {
            "model": self._model,
            "instructions": SYSTEM_PROMPT,
            "input": self.build_input(prompt),
            "text_format": AgentOutput,
        }
        if TOOL_DEFINITIONS:
            request["tools"] = TOOL_DEFINITIONS

        try:
            response = client.responses.parse(**request)
        except AuthenticationError as exc:
            # Log the failure type only; never the key or the request body.
            logger.error("AI provider rejected the configured credentials")
            raise AgentConfigurationError("Invalid AI provider credentials.") from exc
        except RateLimitError as exc:
            logger.warning("AI provider rate limit reached")
            raise AgentProviderError(
                "The AI service is rate limited. Please retry shortly."
            ) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            logger.warning("AI provider is unreachable: %s", type(exc).__name__)
            raise AgentProviderError("The AI service is unreachable.") from exc
        except APIError as exc:
            logger.error("AI provider returned an error: %s", type(exc).__name__)
            raise AgentProviderError() from exc

        if getattr(response, "status", None) == "failed":
            logger.error("AI provider reported a failed response")
            raise AgentProviderError()

        self._raise_on_refusal(response)

        parsed = response.output_parsed
        if parsed is None:
            logger.error("AI provider returned no parsed structured output")
            raise AgentEmptyResponseError()

        return parsed

    @staticmethod
    def _raise_on_refusal(response: Any) -> None:
        """Detect a refusal block anywhere in the response output."""
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "refusal":
                    raise AgentRefusalError()
