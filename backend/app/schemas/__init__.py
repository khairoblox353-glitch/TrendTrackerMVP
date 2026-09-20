"""Pydantic transport schemas (spec 11).

These model the public wire format only. They are the contract between FastAPI and the
Next.js client, and a change here is a change to `frontend/types/api.ts` too.
"""

from app.schemas.article import ArticleDetail, ArticleSummary
from app.schemas.category import CategoryDetail, CategorySummary
from app.schemas.common import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ORMModel,
    Page,
)
from app.schemas.ingestion import HealthResponse, IngestionRequest, RecalculateRequest
from app.schemas.refs import (
    CategoryRef,
    SnapshotPoint,
    SourceRef,
    TopicRef,
    TrendingTopicRef,
)
from app.schemas.trend import TrendDetail, TrendHistory, TrendSummary

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ArticleDetail",
    "ArticleSummary",
    "CategoryDetail",
    "CategoryRef",
    "CategorySummary",
    "HealthResponse",
    "IngestionRequest",
    "ORMModel",
    "Page",
    "RecalculateRequest",
    "SnapshotPoint",
    "SourceRef",
    "TopicRef",
    "TrendDetail",
    "TrendHistory",
    "TrendSummary",
    "TrendingTopicRef",
]
