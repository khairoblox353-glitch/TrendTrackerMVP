"""LLM-backed classifier (spec 3, spec 8).

Talks to any OpenAI-compatible `/chat/completions` endpoint over httpx, so OpenAI,
Azure-style gateways, OpenRouter, Groq or a local Ollama/vLLM server all work by
changing `LLM_BASE_URL` and `LLM_MODEL`.

Failure policy (spec 15, ADR-005): every transport or parsing problem raises
`LLMError`. `services.ingestion` catches it, keeps the article, and stores
`processing_status = 'failed'`. Classification can never abort ingestion.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai.base import ClassificationResult, Classifier, canonical_category
from app.ai.prompts import (
    RETRY_INSTRUCTION,
    TREND_SUMMARY_SYSTEM_PROMPT,
    TREND_SUMMARY_USER_PROMPT,
    USER_PROMPT,
    build_system_prompt,
)
from app.config import Settings
from app.config import settings as default_settings
from app.services.text import clean_whitespace, truncate

logger = logging.getLogger(__name__)

_CODE_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(RuntimeError):
    """Raised when the LLM is unreachable, times out, or answers unusably."""


class LLMClassificationPayload(BaseModel):
    """Validated shape of the model's JSON answer (spec 8)."""

    category: str = Field(default="Other")
    topic: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str | None = None

    @field_validator("topic", "summary")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_whitespace(str(value))
        if not cleaned or cleaned.lower() in {"null", "none", "unknown", "n/a"}:
            return None
        return cleaned


def extract_json_object(raw: str) -> dict:
    """Pull a JSON object out of a model response, tolerating code fences and prose."""
    if not raw or not raw.strip():
        raise LLMError("empty response from LLM")

    candidate = _CODE_FENCE.sub("", raw).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(candidate)
        if match is None:
            raise LLMError("LLM response contained no JSON object") from None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMError("LLM response was not a JSON object")
    return parsed


class LLMClassifier(Classifier):
    """Chat-completions classifier with retries and strict validation."""

    name = "llm"

    def __init__(
        self,
        config: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or default_settings
        if not self.config.llm_api_key:
            raise LLMError("LLM_API_KEY is not configured")
        self._client = client
        self._system_prompt = build_system_prompt()

    # ---- HTTP plumbing -------------------------------------------------
    def _request(self, messages: list[dict[str, str]], *, max_tokens: int = 300) -> str:
        payload = {
            "model": self.config.llm_model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        url = f"{self.config.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.llm_api_key}",
            "Content-Type": "application/json",
        }

        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=self.config.llm_timeout_seconds)
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM returned HTTP {exc.response.status_code}") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        except ValueError as exc:
            raise LLMError("LLM returned a non-JSON body") from exc
        finally:
            if owns_client:
                client.close()

        try:
            return body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected LLM response shape") from exc

    def _chat(self, messages: list[dict[str, str]], *, max_tokens: int = 300) -> str:
        """Send a request, retrying transient failures and one repair round."""
        attempts = self.config.llm_max_retries + 1
        last_error: LLMError | None = None

        for attempt in range(attempts):
            try:
                return self._request(messages, max_tokens=max_tokens)
            except LLMError as exc:
                last_error = exc
                logger.warning(
                    "LLM attempt %s/%s failed: %s", attempt + 1, attempts, exc
                )

        raise last_error or LLMError("LLM request failed")

    # ---- Public API ----------------------------------------------------
    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        """Classify one article. Raises `LLMError`; never returns a partial guess."""
        if not (title or "").strip():
            raise LLMError("article has no title to classify")

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    title=truncate(title.strip(), 300),
                    description=truncate(clean_whitespace(description) or "(none)", 700),
                ),
            },
        ]

        raw = self._chat(messages)
        try:
            payload = LLMClassificationPayload.model_validate(extract_json_object(raw))
        except (LLMError, ValidationError) as exc:
            logger.warning("LLM answer rejected, asking for a repair: %s", exc)
            raw = self._chat(messages + [{"role": "user", "content": RETRY_INSTRUCTION}])
            try:
                payload = LLMClassificationPayload.model_validate(extract_json_object(raw))
            except (LLMError, ValidationError) as retry_exc:
                raise LLMError(f"LLM answer could not be used: {retry_exc}") from retry_exc

        return ClassificationResult(
            category=canonical_category(payload.category),
            topic=truncate(payload.topic, 200) if payload.topic else None,
            confidence=payload.confidence,
            summary=truncate(payload.summary, 300) if payload.summary else None,
            provider=self.name,
        )

    def summarize(self, title: str, descriptions: list[str]) -> str | None:
        """One short trend summary from recent titles (R12). Raises `LLMError`."""
        titles = [truncate(clean_whitespace(item) or "", 160) for item in descriptions if item]
        if not titles:
            raise LLMError("no article titles available for a summary")

        messages = [
            {"role": "system", "content": TREND_SUMMARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": TREND_SUMMARY_USER_PROMPT.format(
                    category="",
                    topic=title,
                    titles="\n".join(f"- {item}" for item in titles[:12]),
                ),
            },
        ]
        summary = clean_whitespace(self._chat(messages, max_tokens=200))
        return truncate(summary, 300) if summary else None
