"""Pydantic schemas for the agent API and structured AI output."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_PROMPT_LENGTH = 4000


class AgentRunRequest(BaseModel):
    """User request to run the agent."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PROMPT_LENGTH,
        description="The question or task for the AI agent.",
        examples=["Explain vector databases to a first-year CS student."],
    )

    @field_validator("prompt")
    @classmethod
    def _strip_prompt(cls, value: str) -> str:
        """Reject whitespace-only prompts and store the trimmed prompt."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("prompt must not be empty")
        return stripped


class AgentOutput(BaseModel):
    """Structured output produced by the model.

    This schema is passed directly to the OpenAI SDK's structured-output
    parser, so the model's response is validated into this model.
    """

    answer: str = Field(
        ..., description="A direct, self-contained answer to the prompt."
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Three to five concise bullet points capturing the essentials.",
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="Useful questions the user might ask next.",
    )


class AgentRunResponse(BaseModel):
    """Result of a successful agent run, as stored in the database."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Identifier of the persisted agent task.")
    result: AgentOutput = Field(..., description="Structured model output.")
    created_at: datetime = Field(
        ..., description="UTC timestamp when the task was stored."
    )
