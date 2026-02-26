"""
Reusable pagination utilities for MOH TIME OS API.

Features:
- PaginatedResponse: Pydantic model for paginated API responses
- paginate(): Helper to slice and wrap query results
- PaginationParams: FastAPI dependency for pagination query parameters
- CursorPaginatedResponse: Model for cursor-based pagination
"""

from typing import Any, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(ge=1, default=1, description="Page number (1-indexed)")
    page_size: int = Field(ge=1, le=500, default=50, description="Items per page (1-500)")


class PaginatedResponse(BaseModel):
    """Standard paginated response model."""

    data: list[Any] = Field(..., description="Items on this page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class CursorPaginatedResponse(BaseModel):
    """Cursor-based paginated response for real-time data."""

    data: list[Any] = Field(..., description="Items")
    next_cursor: str | None = Field(None, description="Cursor for next page (if has_more=True)")
    has_more: bool = Field(..., description="Whether more items exist")


def pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
) -> PaginationParams:
    """FastAPI dependency to extract pagination parameters from query string."""
    return PaginationParams(page=page, page_size=page_size)


def paginate(
    items: list[Any],
    page: int,
    page_size: int,
) -> PaginatedResponse:
    """
    Slice query results and wrap in PaginatedResponse.

    Args:
        items: Full list of items to paginate
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        PaginatedResponse with sliced data and metadata

    Raises:
        ValueError: If page or page_size are invalid
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    total = len(items)
    total_pages = (total + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    data = items[start_idx:end_idx]

    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
