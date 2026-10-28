"""AI agent service built on the native OpenAI Python SDK.

The model only phrases a decision the banking engine has already computed. It
receives the ``BillDecision`` JSON (never raw transactions), returns a
``RecommendationDraft``, and the draft is checked against the decision before
use. Any failure falls back to the deterministic rules text, so the dashboard
never depends on the provider being up.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
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
from app.schemas.banking import round_money
from app.schemas.insights import AgentRecommendation, BillDecision, RecommendationDraft
from app.services.banking.rules import rules_recommendation
from app.services.errors import (
    AgentConfigurationError,
    AgentEmptyResponseError,
    AgentProviderError,
    AgentRefusalError,
    AgentServiceError,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the assistant of a bank. A deterministic engine has already analysed the
client's accounts and decided how to avoid an overdraft. You receive that
decision as JSON. Your only job is to explain it to the client in plain English.

Rules:
- Use only numbers that appear in the JSON. Never calculate, estimate or round
  a new number. Write amounts with two decimals followed by RON.
- recommended_option_id must be copied exactly from the JSON.
- status is "no_risk" if and only if no_action_needed is true; then
  recommended_option_id is null, trade_offs is empty, and you reassure briefly.
- Recommend only the option the engine recommended. Mention other options only
  in trade_offs, one bullet each, with their cost.
- headline: one sentence, the action to take.
- reasons: 3 to 5 short bullets. Each states one decision and why: when and why
  the account goes negative, what doing nothing would cost, why the recommended
  option is cheaper, and what it protects (for example accrued savings interest).
- Do not comment on past spending habits and do not give budgeting advice for
  the future. Do not add disclaimers. Address the client as "you".
"""

_AMOUNT = re.compile(r"\d[\d,]*\.\d+")


class AIAgentService:
    """Turns a ``BillDecision`` into a client-facing recommendation."""

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
    def build_input(decision: BillDecision) -> str:
        return "Pre-computed decision (JSON):\n" + decision.model_dump_json(indent=2)

    def draft(self, decision: BillDecision) -> RecommendationDraft:
        """Call the model with structured output. Raises ``AgentServiceError``."""
        client = self._get_client()
        try:
            response = client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=self.build_input(decision),
                text_format=RecommendationDraft,
            )
        except AuthenticationError as exc:
            # Log the failure type only; never the key or the request body.
            logger.error("AI provider rejected the configured credentials")
            raise AgentConfigurationError("Invalid AI provider credentials.") from exc
        except RateLimitError as exc:
            logger.warning("AI provider rate limit reached")
            raise AgentProviderError("The AI service is rate limited.") from exc
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

    def recommend(self, decision: BillDecision) -> AgentRecommendation:
        """Model wording when it is available and consistent; rules otherwise."""
        if self._client is None and not self._api_key:
            return rules_recommendation(decision, "AI provider not configured")
        try:
            draft = self.draft(decision)
        except AgentServiceError as exc:
            logger.warning("Using rules recommendation: %s", type(exc).__name__)
            return rules_recommendation(decision, exc.public_message)

        problem = check_draft(draft, decision)
        if problem is not None:
            logger.warning("Model output rejected: %s", problem)
            return rules_recommendation(decision, f"Model output rejected: {problem}")
        return AgentRecommendation(**draft.model_dump(), generated_by="llm")

    @staticmethod
    def _raise_on_refusal(response: Any) -> None:
        """Detect a refusal block anywhere in the response output."""
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "refusal":
                    raise AgentRefusalError()


def _known_amounts(value: Any, found: set[Decimal]) -> set[Decimal]:
    if isinstance(value, bool):
        return found
    if isinstance(value, (int, float)):
        found.add(round_money(abs(Decimal(str(value)))))
    elif isinstance(value, str):
        for match in _AMOUNT.findall(value):
            _known_amounts(float(match.replace(",", "")), found)
    elif isinstance(value, dict):
        for item in value.values():
            _known_amounts(item, found)
    elif isinstance(value, list):
        for item in value:
            _known_amounts(item, found)
    return found


def check_draft(draft: RecommendationDraft, decision: BillDecision) -> str | None:
    """Return why the draft cannot be shown, or ``None`` if it is consistent."""
    expected_status = "no_risk" if decision.no_action_needed else "action_required"
    if draft.status != expected_status:
        return "status does not match the decision"
    if draft.recommended_option_id != decision.recommended_option_id:
        return "recommended option differs from the engine"
    if not draft.headline.strip() or not draft.reasons:
        return "empty recommendation"

    known = _known_amounts(json.loads(decision.model_dump_json()), set())
    text = " ".join([draft.headline, *draft.reasons, *draft.trade_offs])
    for match in _AMOUNT.findall(text):
        digits = match.replace(",", "")
        # Rates like 0.0012 are not money; only two-decimal figures are checked.
        if len(digits.split(".")[1]) != 2:
            continue
        try:
            amount = round_money(Decimal(digits))
        except InvalidOperation:
            continue
        if amount not in known:
            return f"amount {match} is not in the decision"
    return None
