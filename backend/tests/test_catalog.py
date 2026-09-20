"""Catalog tests (spec 4, spec 8).

The taxonomy feeds seeding, the collector defaults and the offline classifier, so these
tests pin the invariants other modules rely on.
"""

from __future__ import annotations

from app.catalog import (
    CATEGORIES,
    CATEGORY_KEYWORDS,
    DEFAULT_SOURCES,
    TOPIC_KEYWORDS,
    all_topic_seeds,
    category_seed,
)
from app.services.text import normalize_name


class TestCategories:
    def test_exactly_five_categories(self):
        assert len(CATEGORIES) == 5

    def test_the_specified_categories_and_slugs(self):
        assert {(category.name, category.slug) for category in CATEGORIES} == {
            ("AI", "ai"),
            ("Technology", "technology"),
            ("Finance", "finance"),
            ("Gaming", "gaming"),
            ("Health", "health"),
        }

    def test_every_category_has_a_description_and_keywords(self):
        for category in CATEGORIES:
            assert category.description
            assert category.keywords

    def test_every_category_has_four_curated_topics(self):
        for category in CATEGORIES:
            assert len(category.topics) == 4, category.slug

    def test_twenty_curated_topics_in_total(self):
        assert len(all_topic_seeds()) == 20

    def test_topic_names_are_unique_within_a_category(self):
        for category in CATEGORIES:
            names = [topic.name for topic in category.topics]
            assert len(names) == len(set(names)), category.slug

    def test_topic_names_are_title_cased_and_short(self):
        for _, topic in all_topic_seeds():
            assert topic.name[0].isupper()
            assert len(topic.name.split()) <= 6
            assert topic.description

    def test_category_slugs_are_url_safe(self):
        for category in CATEGORIES:
            assert normalize_name(category.slug).replace(" ", "-") == category.slug

    def test_lookup_by_slug(self):
        assert category_seed("ai") is not None
        assert category_seed("unknown") is None


class TestDerivedLookups:
    def test_every_category_has_a_keyword_entry(self):
        assert set(CATEGORY_KEYWORDS) == {category.slug for category in CATEGORIES}

    def test_every_category_has_topic_keywords(self):
        assert set(TOPIC_KEYWORDS) == {category.slug for category in CATEGORIES}

    def test_topic_keywords_align_with_the_taxonomy(self):
        for category in CATEGORIES:
            declared = {topic.name for topic in category.topics}
            mapped = {name for name, _ in TOPIC_KEYWORDS[category.slug]}
            assert declared == mapped

    def test_every_topic_has_keywords(self):
        for category in CATEGORIES:
            for name, keywords in TOPIC_KEYWORDS[category.slug]:
                assert keywords, f"{name} has no keywords"


class TestDefaultSources:
    def test_sources_are_present(self):
        assert len(DEFAULT_SOURCES) >= 8

    def test_feed_urls_are_unique(self):
        feeds = [source.feed_url for source in DEFAULT_SOURCES]
        assert len(feeds) == len(set(feeds))

    def test_every_source_uses_https(self):
        for source in DEFAULT_SOURCES:
            assert source.feed_url.startswith("https://"), source.name
            assert source.url.startswith("https://"), source.name

    def test_every_source_has_a_name_and_a_known_category(self):
        known = {category.slug for category in CATEGORIES}
        for source in DEFAULT_SOURCES:
            assert source.name
            assert source.category_slug in known, source.name

    def test_every_category_is_covered_by_at_least_one_feed(self):
        covered = {source.category_slug for source in DEFAULT_SOURCES}
        assert covered == {category.slug for category in CATEGORIES}

    def test_load_bearing_sites_are_not_used(self):
        # Placeholder or aggregator domains would make the default demo unreliable.
        forbidden = ("localhost", "example.com", "test.")
        for source in DEFAULT_SOURCES:
            assert not any(token in source.feed_url for token in forbidden), source.name
