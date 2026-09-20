"""Category endpoints (spec 11, spec 12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import NotFoundError
from app.schemas.category import CategoryDetail, CategorySummary
from app.services import trends as trend_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategorySummary], summary="List the five categories")
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    return trend_service.category_summaries(db)


@router.get("/{slug}", response_model=CategoryDetail, summary="Category with its top trends")
def get_category(slug: str, db: Session = Depends(get_db)) -> dict:
    payload = trend_service.get_category(db, slug)
    if payload is None:
        raise NotFoundError(f"Category '{slug}' not found", {"slug": slug})
    return payload
