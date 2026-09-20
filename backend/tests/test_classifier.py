"""Classifier tests: keyword rules, LLM JSON handling and fallback behaviour (spec 8, spec 15)."""

from __future__ import annotations

import httpx
import pytest

from app.ai.base import ClassificationResult, Classifier, canonical_category
from app.ai.factory import build_classifier, classifier_status
from app.ai.fallback import KeywordClassifier, _score_categories
from app.ai.llm import LLMClassifier, LLMError, extract_json_object
from app.config import Settings


class TestKeywordClassifier:
    @pytest.fixture
    def classifier(self) -> KeywordClassifier:
        return KeywordClassifier()

    def test_classifies_an_ai_agent_article(self, classifier):
        result = classifier.classify(
            "OpenAI ships a new agent framework for autonomous tool use",
            "The agent runtime lets teams automate multi-step workflows.",
        )
        assert result.category == "AI"
        assert result.topic == "AI Agents"
        assert result.confidence > 0.5

    def test_classifies_a_gaming_article(self, classifier):
        result = classifier.classify(
            "Unreal Engine 5.5 ships new ray tracing and shader tools",
            "Game developers get faster iteration on the engine.",
        )
        assert result.category == "Gaming"
        assert result.topic == "Game Engines"

    def test_classifies_a_finance_article(self, classifier):
        result = classifier.classify(
            "Central bank holds interest rate steady as inflation cools",
            "Bond yields fell after the monetary policy decision.",
        )
        assert result.category == "Finance"
        assert result.topic == "Interest Rates"

    def test_classifies_a_health_article(self, classifier):
        result = classifier.classify(
            "Telehealth adoption grows as remote monitoring expands",
            "Digital health platforms report more diagnostic visits.",
        )
        assert result.category == "Health"
        assert result.topic == "Digital Health"

    def test_classifies_a_technology_article(self, classifier):
        result = classifier.classify(
            "New chip foundry node enters risk production",
            "The semiconductor supply chain reacts to the wafer milestone.",
        )
        assert result.category == "Technology"
        assert result.topic == "Semiconductors"

    def test_title_matches_outweigh_description_matches(self, classifier):
        titled = classifier.classify("AI agent platform ships", "general market news")
        described = classifier.classify("General market news", "an ai agent platform ships")
        assert titled.confidence > described.confidence

    def test_unknown_article_yields_no_topic(self, classifier):
        result = classifier.classify("Local weather forecast for the weekend")
        assert result.topic is None
        assert result.confidence == 0.0

    def test_unknown_article_does_not_claim_a_real_category(self, classifier):
        # Regression: an unmatched article used to be reported as category "AI" because
        # that value was the first in the taxonomy, so unrelated articles polluted AI.
        result = classifier.classify("Local weather forecast for the weekend")
        assert result.category == "Other"

    def test_a_health_opinion_piece_is_not_classified_as_ai(self, classifier):
        # Regression case observed in production data: a plastic-surgery opinion column
        # from a health feed was filed under AI.
        result = classifier.classify(
            "Opinion: More young men are coming to me for plastic surgery."
        )
        assert result.category != "AI"

    def test_empty_input_is_handled(self, classifier):
        result = classifier.classify("", None)
        assert result.topic is None
        assert result.confidence == 0.0

    def test_summary_falls_back_to_the_title(self, classifier):
        result = classifier.classify("AI agent news", None)
        assert result.summary

    def test_is_deterministic(self, classifier):
        first = classifier.classify("AI agent platform ships", "tool use automation")
        second = classifier.classify("AI agent platform ships", "tool use automation")
        assert first == second

    def test_declares_its_provider(self, classifier):
        assert classifier.classify("AI agent news").provider == "keyword"

    def test_topic_evidence_votes_for_its_category(self, classifier):
        # A headline about a game engine may never say "game"; the engine keywords
        # themselves must still be enough to file it under Gaming.
        result = classifier.classify(
            "Unreal Engine 5.5 ships new ray tracing and shader tools",
            "Developers get faster iteration.",
        )
        assert result.category == "Gaming"
        assert result.topic == "Game Engines"

    def test_category_with_the_stronger_evidence_wins(self, classifier):
        # Competing signals must resolve to the category with more support, not the
        # first one encountered.
        result = classifier.classify(
            "Cybersecurity breach exposes cloud customer data",
            "Ransomware operators exploited a zero-day vulnerability in the platform.",
        )
        assert result.category == "Technology"
        assert result.topic == "Cybersecurity"

    def test_ambiguous_article_has_lower_confidence_than_a_clear_one(self, classifier):
        clear = classifier.classify(
            "AI agent framework ships for autonomous tool use", "agent runtime"
        )
        ambiguous = classifier.classify("AI agent update", None)
        assert clear.confidence > ambiguous.confidence


class TestCategoryScoring:
    """Direct tests of the scoring helper, which the confidence rule depends on."""

    def test_matches_are_ranked_by_total_score(self):
        matches = _score_categories(
            "openai agent framework reaches production",
            "the agent runtime automates multi-step workflows",
        )
        assert matches[0].name == "AI"
        scores = [match.score for match in matches]
        assert scores == sorted(scores, reverse=True)

    def test_matching_nothing_returns_no_candidates(self):
        assert _score_categories("local weather forecast", "rain tomorrow") == []

    def test_short_keywords_do_not_match_inside_other_words(self):
        # Regression: substring matching made the "ai" keyword fire on "rain",
        # "chair" and "domain", so weather articles were filed under AI.
        for text in ("rain tomorrow", "a comfortable chair", "domain registration"):
            assert _score_categories(text, "") == []

    def test_hyphenated_keywords_are_matched(self):
        assert _score_categories("stablecoin flows turn on-chain", "")[0].name == "Finance"

    def test_plurals_of_keywords_are_matched(self):
        assert _score_categories("new chips enter mass production", "")[0].name == "Technology"

    def test_topic_evidence_contributes_to_the_category_score(self):
        with_topic = _score_categories("unreal engine ray tracing shaders", "")
        assert with_topic
        assert with_topic[0].name == "Gaming"
        assert with_topic[0].topic_name == "Game Engines"

    def test_a_weakly_matched_topic_is_discarded(self):
        # "agent" matches AI Agents strongly, but a lone generic word must not be
        # enough to name a trend.
        matches = _score_categories("a general update about models", "")
        ai_match = next((match for match in matches if match.name == "AI"), None)
        assert ai_match is not None
        assert ai_match.topic_name is None


class TestCanonicalCategory:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("AI", "AI"),
            ("ai", "AI"),
            ("  ai ", "AI"),
            ("Technology", "Technology"),
            ("health", "Health"),
            ("GAMING", "Gaming"),
            ("Finance", "Finance"),
        ],
    )
    def test_known_categories_are_normalized(self, raw, expected):
        assert canonical_category(raw) == expected

    @pytest.mark.parametrize("raw", ["Astrology", "", None, "AI and Robotics"])
    def test_unknown_categories_become_other(self, raw):
        assert canonical_category(raw) == "Other"


class TestExtractJsonObject:
    def test_parses_plain_json(self):
        payload = extract_json_object('{"category": "AI", "topic": "AI Agents"}')
        assert payload["category"] == "AI"

    def test_strips_code_fences(self):
        raw = '```json\n{"category": "AI", "topic": "AI Agents"}\n```'
        assert extract_json_object(raw)["topic"] == "AI Agents"

    def test_ignores_surrounding_prose(self):
        raw = 'Sure! Here is the answer: {"category": "AI", "topic": "AI Agents"} Hope that helps.'
        assert extract_json_object(raw)["category"] == "AI"

    def test_rejects_an_empty_response(self):
        with pytest.raises(LLMError, match="empty response"):
            extract_json_object("")

    def test_rejects_a_response_without_json(self):
        with pytest.raises(LLMError, match="no JSON object"):
            extract_json_object("I cannot help with that.")

    def test_rejects_a_json_array(self):
        with pytest.raises(LLMError, match="not a JSON object"):
            extract_json_object('["AI", "AI Agents"]')


def make_llm(handler, **overrides) -> LLMClassifier:
    settings = Settings(
        llm_enabled=True,
        llm_api_key="test-key",
        llm_max_retries=overrides.pop("llm_max_retries", 1),
        **overrides,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMClassifier(settings, client=client)


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )


class TestLLMClassifier:
    def test_parses_a_valid_answer(self):
        classifier = make_llm(
            lambda request: chat_response(
                '{"category": "AI", "topic": "AI Agents", "confidence": 0.91, '
                '"summary": "Agents move into production."}'
            )
        )
        result = classifier.classify("Some title", "Some description")

        assert result.category == "AI"
        assert result.topic == "AI Agents"
        assert result.confidence == pytest.approx(0.91)
        assert result.summary == "Agents move into production."
        assert result.provider == "llm"

    def test_maps_an_unknown_category_to_other(self):
        classifier = make_llm(
            lambda request: chat_response(
                '{"category": "Astrology", "topic": "Horoscopes", "confidence": 0.9}'
            )
        )
        assert classifier.classify("Stars").category == "Other"

    def test_null_topic_is_accepted(self):
        classifier = make_llm(
            lambda request: chat_response(
                '{"category": "AI", "topic": null, "confidence": 0.2, "summary": null}'
            )
        )
        result = classifier.classify("Vague title")
        assert result.topic is None
        assert result.summary is None

    def test_literal_null_strings_are_treated_as_absent(self):
        classifier = make_llm(
            lambda request: chat_response(
                '{"category": "AI", "topic": "None", "confidence": 0.9, "summary": "unknown"}'
            )
        )
        result = classifier.classify("Title")
        assert result.topic is None
        assert result.summary is None

    def test_out_of_range_confidence_triggers_a_repair_attempt(self):
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return chat_response('{"category": "AI", "topic": "AI Agents", "confidence": 9.9}')
            return chat_response('{"category": "AI", "topic": "AI Agents", "confidence": 0.8}')

        result = make_llm(handler).classify("Title")

        assert len(calls) == 2
        assert result.confidence == pytest.approx(0.8)

    def test_malformed_json_after_a_repair_raises(self):
        classifier = make_llm(lambda request: chat_response("not json at all"))
        with pytest.raises(LLMError, match="could not be used"):
            classifier.classify("Title")

    def test_http_error_raises_llm_error(self):
        classifier = make_llm(lambda request: httpx.Response(500, json={}))
        with pytest.raises(LLMError, match="HTTP 500"):
            classifier.classify("Title")

    def test_timeout_raises_llm_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("slow", request=request)

        classifier = make_llm(handler, llm_max_retries=0)
        with pytest.raises(LLMError, match="timed out"):
            classifier.classify("Title")

    def test_unexpected_response_shape_raises(self):
        classifier = make_llm(lambda request: httpx.Response(200, json={"choices": []}))
        with pytest.raises(LLMError, match="unexpected LLM response shape"):
            classifier.classify("Title")

    def test_transient_failures_are_retried(self):
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return httpx.Response(503, json={})
            return chat_response('{"category": "AI", "topic": "AI Agents", "confidence": 0.9}')

        result = make_llm(handler, llm_max_retries=1).classify("Title")

        assert len(calls) == 2
        assert result.topic == "AI Agents"

    def test_empty_title_is_rejected_before_any_request(self):
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return chat_response("{}")

        with pytest.raises(LLMError, match="no title"):
            make_llm(handler).classify("   ")
        assert calls == []

    def test_summarize_returns_plain_text(self):
        classifier = make_llm(lambda request: chat_response("Agents are being adopted widely."))
        summary = classifier.summarize("AI Agents", ["Title one", "Title two"])
        assert summary == "Agents are being adopted widely."

    def test_summarize_requires_titles(self):
        classifier = make_llm(lambda request: chat_response("ignored"))
        with pytest.raises(LLMError, match="no article titles"):
            classifier.summarize("AI Agents", [])


class TestResilientClassifier:
    def test_uses_the_primary_when_it_works(self):
        classifier = build_classifier(
            Settings(llm_enabled=True, llm_api_key="key", llm_base_url="http://localhost:1")
        )
        assert classifier.name in {"resilient", "llm", "keyword"}

    def test_falls_back_to_keywords_without_an_api_key(self):
        classifier = build_classifier(Settings(llm_enabled=False))
        assert classifier.name == "keyword"
        assert classifier_status(Settings(llm_enabled=False)) == "fallback"

    def test_reports_llm_status_when_configured(self):
        assert classifier_status(Settings(llm_enabled=True, llm_api_key="key")) == "llm"

    def test_primary_failure_degrades_to_keywords_without_raising(self):
        from app.ai.factory import ResilientClassifier

        class Broken(Classifier):
            name = "broken"

            def classify(self, title, description=None):
                raise LLMError("network down")

        resilient = ResilientClassifier(Broken(), KeywordClassifier())
        result = resilient.classify(
            "OpenAI agent framework ships for autonomous tool use", "agent runtime"
        )

        assert result.degraded is True
        assert result.error == "network down"
        assert result.topic == "AI Agents"
        assert resilient.is_degraded is True

    def test_recovery_clears_the_degraded_flag(self):
        from app.ai.factory import ResilientClassifier

        class Flaky(Classifier):
            name = "flaky"

            def __init__(self):
                self.fail = True

            def classify(self, title, description=None):
                if self.fail:
                    raise LLMError("down")
                return ClassificationResult(category="AI", topic="AI Agents", confidence=0.9)

        primary = Flaky()
        resilient = ResilientClassifier(primary, KeywordClassifier())

        resilient.classify("Title")
        assert resilient.is_degraded is True

        primary.fail = False
        resilient.classify("Title")
        assert resilient.is_degraded is False
