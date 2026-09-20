"""Prompt templates for the LLM classifier (spec 8).

The prompt is explicit that the model must answer with JSON only and must pick a
topic from the category's existing vocabulary when one fits. That keeps the topic
space from fragmenting into near-duplicate names.
"""

from __future__ import annotations

from app.catalog import CATEGORIES

SYSTEM_PROMPT = """You are a news classification engine for a trend-tracking product.

You receive the title and short description of one news article. You return a single
JSON object and nothing else.

Rules:
1. "category" MUST be exactly one of: {categories}. If nothing fits, use "Other".
2. "topic" is a short, specific subject label inside that category, in Title Case,
   at most 6 words. Prefer one of the known topics listed below when it fits.
3. "confidence" is a number between 0 and 1 describing how sure you are about the topic.
   Use a value below 0.55 when the article is ambiguous or generic.
4. "summary" is one neutral sentence of at most 200 characters. No marketing language.
5. Never invent facts that are not present in the input.

Known topics per category:
{taxonomy}

Respond with exactly this shape:
{{"category": "...", "topic": "...", "confidence": 0.0, "summary": "..."}}"""

USER_PROMPT = """Title: {title}

Description: {description}"""

RETRY_INSTRUCTION = (
    "Your previous answer was not valid JSON matching the required shape. "
    "Reply with the JSON object only, no prose, no code fences."
)

TREND_SUMMARY_SYSTEM_PROMPT = """You summarise a trend for a dashboard.

You receive a topic name, its category, and the titles of its most recent articles.
Write 1-2 neutral sentences (at most 240 characters) describing what this trend is
about. Describe only what the titles support. No bullet points, no headline, no
marketing language. Reply with plain text only."""

TREND_SUMMARY_USER_PROMPT = """Category: {category}
Topic: {topic}

Recent article titles:
{titles}"""


def build_taxonomy_block() -> str:
    lines: list[str] = []
    for category in CATEGORIES:
        topics = ", ".join(topic.name for topic in category.topics)
        lines.append(f"- {category.name}: {topics}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(
        categories=", ".join(category.name for category in CATEGORIES),
        taxonomy=build_taxonomy_block(),
    )
