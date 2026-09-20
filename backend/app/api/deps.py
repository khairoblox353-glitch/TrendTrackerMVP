"""Shared FastAPI dependencies: session, pagination and sort validation (spec 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fastapi import Query

from app.api.errors import ValidationError
from app.database import get_db
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

__all__ = ["get_db", "Pagination", "pagination_params"]


@dataclass(slots=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    ),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


def parse_iso_date(value: str | None, field: str) -> date | None:
    """Parse an optional ISO date, rejecting bad input with a 422."""
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            f"'{value}' is not a valid ISO date for '{field}'", {"field": field}
        ) from exc
