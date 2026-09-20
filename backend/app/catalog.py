"""Canonical MVP taxonomy (spec 4, spec 8, spec 17).

One place defines the five categories, the initial topic vocabulary, the keyword
rules the offline classifier uses, and the default RSS feeds. Seed data, the
collector defaults and the fallback classifier all read from here, so the taxonomy
cannot drift between components.

This module is data only: no imports from `app.database` or `app.config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TopicSeed:
    name: str
    description: str
    keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CategorySeed:
    name: str
    slug: str
    description: str
    keywords: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[TopicSeed, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SourceSeed:
    name: str
    url: str
    feed_url: str
    category_slug: str | None = None


CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed(
        name="AI",
        slug="ai",
        description="Artificial intelligence, models, agents and the tooling around them.",
        keywords=(
            "ai",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural",
            "llm",
            "gpt",
            "prompt",
            "model",
            "agent",
            "inference",
            "training",
            "openai",
            "anthropic",
            "gemini",
            "claude",
        ),
        topics=(
            TopicSeed(
                name="AI Agents",
                description="Autonomous and semi-autonomous agents that plan and use tools.",
                keywords=(
                    "agent",
                    "agentic",
                    "autonomous",
                    "tool use",
                    "workflow automation",
                    "copilot",
                    "computer use",
                ),
            ),
            TopicSeed(
                name="Large Language Models",
                description="Frontier and open-weight language models and their capabilities.",
                keywords=(
                    "llm",
                    "language model",
                    "gpt",
                    "claude",
                    "gemini",
                    "llama",
                    "mistral",
                    "fine-tune",
                    "context window",
                    "reasoning model",
                ),
            ),
            TopicSeed(
                name="AI Infrastructure",
                description="Compute, accelerators and serving stacks that run AI workloads.",
                keywords=(
                    "gpu",
                    "accelerator",
                    "inference",
                    "data center",
                    "training cluster",
                    "tpu",
                    "nvidia",
                    "serving",
                    "throughput",
                ),
            ),
            TopicSeed(
                name="AI Policy",
                description="Regulation, safety rules and governance of AI systems.",
                keywords=(
                    "regulation",
                    "policy",
                    "safety",
                    "governance",
                    "compliance",
                    "eu ai act",
                    "copyright",
                    "audit",
                ),
            ),
        ),
    ),
    CategorySeed(
        name="Technology",
        slug="technology",
        description="Hardware, software platforms, cloud and security.",
        keywords=(
            "technology",
            "tech",
            "software",
            "hardware",
            "platform",
            "developer",
            "cloud",
            "security",
            "chip",
        ),
        topics=(
            TopicSeed(
                name="Semiconductors",
                description="Chip design, fabrication and the supply chain behind them.",
                keywords=(
                    "chip",
                    "semiconductor",
                    "foundry",
                    "wafer",
                    "node",
                    "lithography",
                    "tsmc",
                    "arm",
                    "silicon",
                ),
            ),
            TopicSeed(
                name="Cloud Computing",
                description="Public cloud, platform services and infrastructure tooling.",
                keywords=(
                    "cloud",
                    "aws",
                    "azure",
                    "google cloud",
                    "kubernetes",
                    "serverless",
                    "saas",
                    "region",
                    "outage",
                ),
            ),
            TopicSeed(
                name="Cybersecurity",
                description="Vulnerabilities, breaches, ransomware and defensive tooling.",
                keywords=(
                    "cybersecurity",
                    "breach",
                    "ransomware",
                    "malware",
                    "vulnerability",
                    "zero-day",
                    "phishing",
                    "exploit",
                    "patch",
                ),
            ),
            TopicSeed(
                name="Consumer Devices",
                description="Phones, laptops, wearables and the software that ships with them.",
                keywords=(
                    "smartphone",
                    "laptop",
                    "tablet",
                    "wearable",
                    "headset",
                    "review",
                    "launch",
                    "device",
                    "gadget",
                ),
            ),
        ),
    ),
    CategorySeed(
        name="Finance",
        slug="finance",
        description="Markets, funding and consumer financial services.",
        keywords=(
            "finance",
            "market",
            "investor",
            "stock",
            "earnings",
            "economy",
            "bank",
            "fund",
            "trading",
        ),
        topics=(
            TopicSeed(
                name="Crypto Markets",
                description="Digital asset prices, exchanges and on-chain activity.",
                keywords=(
                    "crypto",
                    "bitcoin",
                    "ethereum",
                    "blockchain",
                    "token",
                    "exchange",
                    "stablecoin",
                    "etf",
                    "on-chain",
                ),
            ),
            TopicSeed(
                name="Interest Rates",
                description="Central bank policy, inflation prints and bond markets.",
                keywords=(
                    "interest rate",
                    "central bank",
                    "federal reserve",
                    "inflation",
                    "bond",
                    "yield",
                    "rate cut",
                    "monetary",
                ),
            ),
            TopicSeed(
                name="Startup Funding",
                description="Venture rounds, valuations and startup financing conditions.",
                keywords=(
                    "startup",
                    "funding",
                    "series a",
                    "seed round",
                    "valuation",
                    "venture",
                    "raise",
                    "unicorn",
                ),
            ),
            TopicSeed(
                name="Digital Banking",
                description="Neobanks, payments and embedded financial products.",
                keywords=(
                    "fintech",
                    "neobank",
                    "payment",
                    "wallet",
                    "open banking",
                    "card",
                    "remittance",
                    "ledger",
                ),
            ),
        ),
    ),
    CategorySeed(
        name="Gaming",
        slug="gaming",
        description="Games, players, studios and the hardware they run on.",
        keywords=(
            "game",
            "gaming",
            "player",
            "studio",
            "console",
            "esports",
            "steam",
            "playstation",
            "xbox",
            "nintendo",
        ),
        topics=(
            TopicSeed(
                name="Game Releases",
                description="Launches, reviews and sales for new and upcoming games.",
                keywords=(
                    "release",
                    "launch",
                    "review",
                    "sequel",
                    "early access",
                    "remaster",
                    "sales",
                    "patch notes",
                ),
            ),
            TopicSeed(
                name="Esports",
                description="Competitive leagues, tournaments and team news.",
                keywords=(
                    "esports",
                    "tournament",
                    "league",
                    "championship",
                    "roster",
                    "prize pool",
                    "competitive",
                ),
            ),
            TopicSeed(
                name="Game Engines",
                description="Engines, graphics techniques and development tooling.",
                keywords=(
                    "engine",
                    "unreal",
                    "unity",
                    "godot",
                    "ray tracing",
                    "shader",
                    "sdk",
                    "optimization",
                ),
            ),
            TopicSeed(
                name="Console Hardware",
                description="Consoles, handhelds and gaming PCs.",
                keywords=(
                    "console",
                    "handheld",
                    "playstation",
                    "xbox",
                    "switch",
                    "gpu",
                    "steam deck",
                    "controller",
                ),
            ),
        ),
    ),
    CategorySeed(
        name="Health",
        slug="health",
        description="Medicine, wellbeing, care delivery and public health.",
        keywords=(
            "health",
            "medical",
            "patient",
            "clinical",
            "treatment",
            "disease",
            "care",
            "wellness",
        ),
        topics=(
            TopicSeed(
                name="Biotech",
                description="Drug development, trials and life-science platforms.",
                keywords=(
                    "biotech",
                    "trial",
                    "drug",
                    "therapy",
                    "gene",
                    "crispr",
                    "fda",
                    "antibody",
                    "biomarker",
                ),
            ),
            TopicSeed(
                name="Mental Health",
                description="Mental wellbeing, access to care and digital therapy.",
                keywords=(
                    "mental health",
                    "depression",
                    "anxiety",
                    "therapy",
                    "burnout",
                    "counselling",
                    "wellbeing",
                    "sleep",
                ),
            ),
            TopicSeed(
                name="Digital Health",
                description="Telehealth, wearables and health data platforms.",
                keywords=(
                    "telehealth",
                    "digital health",
                    "remote monitoring",
                    "wearable",
                    "health record",
                    "app",
                    "sensor",
                    "diagnostic",
                ),
            ),
            TopicSeed(
                name="Public Health",
                description="Population health, outbreaks, vaccination and health policy.",
                keywords=(
                    "public health",
                    "outbreak",
                    "vaccine",
                    "epidemic",
                    "who",
                    "screening",
                    "prevention",
                    "mortality",
                ),
            ),
        ),
    ),
)

DEFAULT_SOURCES: tuple[SourceSeed, ...] = (
    SourceSeed(
        "Google AI Blog",
        "https://blog.google/technology/ai/",
        "https://blog.google/technology/ai/rss/",
        "ai",
    ),
    SourceSeed(
        "Hugging Face Blog",
        "https://huggingface.co/blog",
        "https://huggingface.co/blog/feed.xml",
        "ai",
    ),
    SourceSeed("TechCrunch", "https://techcrunch.com", "https://techcrunch.com/feed/", "technology"),
    SourceSeed(
        "Ars Technica",
        "https://arstechnica.com",
        "https://feeds.arstechnica.com/arstechnica/index",
        "technology",
    ),
    SourceSeed(
        "The Verge",
        "https://www.theverge.com",
        "https://www.theverge.com/rss/index.xml",
        "technology",
    ),
    SourceSeed(
        "CoinDesk",
        "https://www.coindesk.com",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "finance",
    ),
    SourceSeed(
        "Yahoo Finance",
        "https://finance.yahoo.com",
        "https://finance.yahoo.com/news/rssindex",
        "finance",
    ),
    SourceSeed("PC Gamer", "https://www.pcgamer.com", "https://www.pcgamer.com/rss/", "gaming"),
    SourceSeed("Eurogamer", "https://www.eurogamer.net", "https://www.eurogamer.net/feed", "gaming"),
    SourceSeed("Stat News", "https://www.statnews.com", "https://www.statnews.com/feed/", "health"),
    SourceSeed("WHO News", "https://www.who.int", "https://www.who.int/rss-feeds/news-english.xml", "health"),
)


def category_seed(slug: str) -> CategorySeed | None:
    return next((category for category in CATEGORIES if category.slug == slug), None)


def all_topic_seeds() -> list[tuple[CategorySeed, TopicSeed]]:
    return [(category, topic) for category in CATEGORIES for topic in category.topics]


# ---- Derived lookups used by the offline classifier -------------------------
# Built once at import time so classification does no repeated scanning.

CATEGORY_BY_SLUG: dict[str, CategorySeed] = {category.slug: category for category in CATEGORIES}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    category.slug: category.keywords for category in CATEGORIES
}

TOPIC_KEYWORDS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    category.slug: tuple((topic.name, topic.keywords) for topic in category.topics)
    for category in CATEGORIES
}

