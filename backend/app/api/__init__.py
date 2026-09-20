"""HTTP API layer (spec 11).

Every router only validates input, calls one service function, and serializes the
result (spec 19.11).
"""

from fastapi import APIRouter

from app.api import articles, categories, ingestion, trends

api_router = APIRouter(prefix="/api")
api_router.include_router(categories.router)
api_router.include_router(trends.router)
api_router.include_router(articles.router)
api_router.include_router(ingestion.router)

__all__ = ["api_router"]
