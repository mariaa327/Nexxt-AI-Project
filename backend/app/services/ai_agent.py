"""AI agent service on Amazon Bedrock (Anthropic Claude, Converse API).

The model only phrases a decision the banking engine has already computed. It
receives the ``BillDecision`` JSON (never raw transactions) and must answer by
calling one tool whose input schema is ``RecommendationDraft``; the draft is
then checked against the decision before use. Any failure falls back to the
deterministic rules text, so the dashboard never depends on the provider.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from pydantic import ValidationError

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

TOOL_NAME = "submit_recommendation"

SYSTEM_PROMPT = f"""\
You are the assistant of a bank. A deterministic engine has already analysed the
client's accounts and decided how to avoid an overdraft. You receive that
decision as JSON. Your only job is to explain it to the client in plain English,
by calling the {TOOL_NAME} tool exactly once.

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
  Point out where the client's money actually is (savings balance, available
  credit on the card): the problem is money in the wrong account, not a lack of
  money.
- Do not comment on past spending habits and do not give budgeting advice for
  the future. Do not add disclaimers. Address the client as "you".
"""

# Credentials missing, wrong or expired: a configuration problem, not an outage.
_CREDENTIAL_ERRORS = frozenset(
    {
        "AccessDeniedException",
        "ExpiredTokenException",
        "UnrecognizedClientException",
        "InvalidSignatureException",
    }
)

_AMOUNT = re.compile(r"\d[\d,]*\.\d+")


def _tool_config() -> dict[str, Any]:
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": TOOL_NAME,
                    "description": "Submit the client-facing recommendation.",
                    "inputSchema": {"json": RecommendationDraft.model_json_schema()},
                }
            }
        ],
        # Newer Claude models on Bedrock reject a forced tool choice; the system
        # prompt requires the call, and a reply without it falls back to rules.
        "toolChoice": {"auto": {}},
    }


class AIAgentService:
    """Turns a ``BillDecision`` into a client-facing recommendation."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._model = model or settings.bedrock_model_id
        # Created lazily so importing the app and the health check need no AWS.
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def configured() -> bool:
        return bool(settings.aws_access_key_id and settings.aws_secret_access_key)

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.configured():
                raise AgentConfigurationError()
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.aws_default_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                aws_session_token=settings.aws_session_token,
                config=Config(
                    connect_timeout=5,
                    read_timeout=settings.ai_timeout_seconds,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._client

    @staticmethod
    def build_input(decision: BillDecision) -> str:
        return "Pre-computed decision (JSON):\n" + decision.model_dump_json(indent=2)

    def draft(self, decision: BillDecision) -> RecommendationDraft:
        """Call the model with a forced tool call. Raises ``AgentServiceError``."""
        client = self._get_client()
        try:
            response = client.converse(
                modelId=self._model,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[
                    {"role": "user", "content": [{"text": self.build_input(decision)}]}
                ],
                toolConfig=_tool_config(),
                inferenceConfig={"maxTokens": 1500},
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            # Log the error code only; never credentials or the request body.
            if code in _CREDENTIAL_ERRORS:
                logger.error("Bedrock rejected the credentials: %s", code)
                raise AgentConfigurationError(
                    "AI credentials are invalid or expired."
                ) from exc
            logger.warning("Bedrock returned an error: %s", code)
            raise AgentProviderError() from exc
        except NoCredentialsError as exc:
            raise AgentConfigurationError() from exc
        except BotoCoreError as exc:
            # Timeouts and connection failures.
            logger.warning("Bedrock is unreachable: %s", type(exc).__name__)
            raise AgentProviderError("The AI service is unreachable.") from exc

        if response.get("stopReason") in ("guardrail_intervened", "content_filtered"):
            raise AgentRefusalError()

        content = response.get("output", {}).get("message", {}).get("content", [])
        tool_input = next(
            (
                block["toolUse"].get("input")
                for block in content
                if "toolUse" in block and block["toolUse"].get("name") == TOOL_NAME
            ),
            None,
        )
        if tool_input is None:
            logger.error("Bedrock returned no tool call")
            raise AgentEmptyResponseError()
        try:
            return RecommendationDraft.model_validate(tool_input)
        except ValidationError as exc:
            logger.error(
                "Bedrock tool input failed validation (%d errors)", exc.error_count()
            )
            raise AgentEmptyResponseError() from exc

    def recommend(self, decision: BillDecision) -> AgentRecommendation:
        """Model wording when it is available and consistent; rules otherwise."""
        if self._client is None and not self.configured():
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
