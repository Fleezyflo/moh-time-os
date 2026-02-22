"""
Tests for pagination utilities.

Tests cover:
- PaginatedResponse model validation
- paginate() helper with various page sizes
- Edge cases (empty list, last page, oversized page)
- Cursor pagination model
- PaginationParams dependency
"""

import pytest
from pydantic import ValidationError

from lib.api.pagination import (
    CursorPaginatedResponse,
    PaginatedResponse,
    PaginationParams,
    paginate,
)


class TestPaginationParams:
    """Tests for PaginationParams model."""

    def test_default_values(self):
        """Test default pagination parameters."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 50

    def test_custom_values(self):
        """Test setting custom pagination parameters."""
        params = PaginationParams(page=3, page_size=100)
        assert params.page == 3
        assert params.page_size == 100

    def test_page_must_be_positive(self):
        """Test that page must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_page_size_must_be_positive(self):
        """Test that page_size must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page_size=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_page_size_must_not_exceed_max(self):
        """Test that page_size is capped at 500."""
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page_size=501)
        assert "less than or equal to 500" in str(exc_info.value)

    def test_negative_page(self):
        """Test that negative page is rejected."""
        with pytest.raises(ValidationError):
            PaginationParams(page=-1)

    def test_negative_page_size(self):
        """Test that negative page_size is rejected."""
        with pytest.raises(ValidationError):
            PaginationParams(page_size=-1)


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_create_response(self):
        """Test creating a paginated response."""
        response = PaginatedResponse(
            data=[{"id": 1}, {"id": 2}],
            total=100,
            page=1,
            page_size=50,
            total_pages=2,
            has_next=True,
            has_prev=False,
        )
        assert response.data == [{"id": 1}, {"id": 2}]
        assert response.total == 100
        assert response.page == 1
        assert response.page_size == 50
        assert response.total_pages == 2
        assert response.has_next is True
        assert response.has_prev is False

    def test_response_serialization(self):
        """Test that response can be serialized to dict."""
        response = PaginatedResponse(
            data=[{"id": 1}],
            total=50,
            page=1,
            page_size=50,
            total_pages=1,
            has_next=False,
            has_prev=False,
        )
        data = response.model_dump()
        assert data["data"] == [{"id": 1}]
        assert data["total"] == 50
        assert "page" in data
        assert "page_size" in data

    def test_response_json(self):
        """Test that response can be converted to JSON."""
        response = PaginatedResponse(
            data=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=0,
            has_next=False,
            has_prev=False,
        )
        json_str = response.model_dump_json()
        assert "data" in json_str
        assert "total" in json_str


class TestPaginateHelper:
    """Tests for paginate() helper function."""

    def test_paginate_first_page(self):
        """Test pagination of first page."""
        items = list(range(1, 151))  # 150 items
        response = paginate(items, page=1, page_size=50)

        assert len(response.data) == 50
        assert response.data == list(range(1, 51))
        assert response.total == 150
        assert response.page == 1
        assert response.page_size == 50
        assert response.total_pages == 3
        assert response.has_next is True
        assert response.has_prev is False

    def test_paginate_middle_page(self):
        """Test pagination of middle page."""
        items = list(range(1, 151))  # 150 items
        response = paginate(items, page=2, page_size=50)

        assert len(response.data) == 50
        assert response.data == list(range(51, 101))
        assert response.page == 2
        assert response.has_next is True
        assert response.has_prev is True

    def test_paginate_last_page(self):
        """Test pagination of last page."""
        items = list(range(1, 151))  # 150 items
        response = paginate(items, page=3, page_size=50)

        assert len(response.data) == 50
        assert response.data == list(range(101, 151))
        assert response.page == 3
        assert response.total_pages == 3
        assert response.has_next is False
        assert response.has_prev is True

    def test_paginate_partial_last_page(self):
        """Test pagination where last page is partial."""
        items = list(range(1, 126))  # 125 items, 50 per page = 3 pages (last is 25)
        response = paginate(items, page=3, page_size=50)

        assert len(response.data) == 25
        assert response.data == list(range(101, 126))
        assert response.total_pages == 3

    def test_paginate_single_page(self):
        """Test pagination when all items fit on one page."""
        items = list(range(1, 11))  # 10 items
        response = paginate(items, page=1, page_size=50)

        assert len(response.data) == 10
        assert response.total == 10
        assert response.total_pages == 1
        assert response.has_next is False
        assert response.has_prev is False

    def test_paginate_empty_list(self):
        """Test pagination of empty list."""
        response = paginate([], page=1, page_size=50)

        assert response.data == []
        assert response.total == 0
        assert response.total_pages == 0
        assert response.has_next is False
        assert response.has_prev is False

    def test_paginate_empty_page_beyond_range(self):
        """Test pagination when page exceeds available pages."""
        items = list(range(1, 11))  # 10 items, 1 page of 50
        response = paginate(items, page=5, page_size=50)

        assert response.data == []
        assert response.total == 10
        assert response.page == 5

    def test_paginate_small_page_size(self):
        """Test pagination with page_size=1."""
        items = list(range(1, 6))  # 5 items
        response = paginate(items, page=2, page_size=1)

        assert response.data == [2]
        assert response.total_pages == 5
        assert response.has_next is True

    def test_paginate_large_page_size(self):
        """Test pagination with very large page_size."""
        items = list(range(1, 101))  # 100 items
        response = paginate(items, page=1, page_size=500)

        assert len(response.data) == 100
        assert response.total_pages == 1

    def test_paginate_invalid_page(self):
        """Test that invalid page raises ValueError."""
        items = list(range(1, 51))
        with pytest.raises(ValueError, match="page must be >= 1"):
            paginate(items, page=0, page_size=50)

    def test_paginate_invalid_page_size(self):
        """Test that invalid page_size raises ValueError."""
        items = list(range(1, 51))
        with pytest.raises(ValueError, match="page_size must be >= 1"):
            paginate(items, page=1, page_size=0)

    def test_paginate_negative_page(self):
        """Test that negative page raises ValueError."""
        items = list(range(1, 51))
        with pytest.raises(ValueError):
            paginate(items, page=-1, page_size=50)

    def test_paginate_complex_objects(self):
        """Test pagination with complex objects (dicts)."""
        items = [{"id": i, "name": f"Item {i}", "value": i * 10} for i in range(1, 101)]
        response = paginate(items, page=1, page_size=25)

        assert len(response.data) == 25
        assert response.data[0]["id"] == 1
        assert response.data[0]["name"] == "Item 1"
        assert response.total == 100
        assert response.total_pages == 4

    def test_paginate_exact_page_boundary(self):
        """Test pagination at exact page boundary."""
        items = list(range(1, 101))  # 100 items, 50 per page
        response = paginate(items, page=2, page_size=50)

        assert len(response.data) == 50
        assert response.data == list(range(51, 101))
        assert response.has_next is False
        assert response.total_pages == 2


class TestCursorPaginatedResponse:
    """Tests for cursor-based pagination response."""

    def test_create_cursor_response_with_more(self):
        """Test creating a cursor paginated response with more data."""
        response = CursorPaginatedResponse(
            data=[{"id": 1}, {"id": 2}],
            next_cursor="abc123",
            has_more=True,
        )
        assert response.data == [{"id": 1}, {"id": 2}]
        assert response.next_cursor == "abc123"
        assert response.has_more is True

    def test_create_cursor_response_no_more(self):
        """Test creating a cursor paginated response without more data."""
        response = CursorPaginatedResponse(
            data=[{"id": 1}],
            next_cursor=None,
            has_more=False,
        )
        assert response.data == [{"id": 1}]
        assert response.next_cursor is None
        assert response.has_more is False

    def test_cursor_response_serialization(self):
        """Test that cursor response can be serialized."""
        response = CursorPaginatedResponse(
            data=[{"id": 1}],
            next_cursor="xyz",
            has_more=True,
        )
        data = response.model_dump()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data

    def test_cursor_response_empty(self):
        """Test cursor response with empty data."""
        response = CursorPaginatedResponse(
            data=[],
            next_cursor=None,
            has_more=False,
        )
        assert response.data == []
        assert response.has_more is False


class TestPaginationEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_paginate_with_unicode_data(self):
        """Test pagination with unicode strings."""
        items = [{"id": i, "name": f"Item {i} 中文 العربية"} for i in range(1, 51)]
        response = paginate(items, page=1, page_size=10)
        assert len(response.data) == 10
        assert "中文" in response.data[0]["name"]

    def test_paginate_preserves_order(self):
        """Test that pagination preserves original order."""
        items = [{"id": i, "order": i} for i in [5, 2, 8, 1, 9, 3, 7, 4, 6]]
        response = paginate(items, page=1, page_size=5)
        assert response.data[0]["id"] == 5
        assert response.data[1]["id"] == 2
        # Order is preserved from original

    def test_paginate_large_dataset(self):
        """Test pagination with large dataset."""
        items = list(range(1, 10001))  # 10,000 items
        response = paginate(items, page=100, page_size=50)

        assert response.total == 10000
        assert response.total_pages == 200
        assert response.data[0] == 4951  # (99 * 50) + 1
        assert response.page == 100

    def test_total_pages_calculation_exact_division(self):
        """Test total_pages calculation when items divide evenly."""
        items = list(range(1, 101))  # 100 items
        response = paginate(items, page=1, page_size=25)
        assert response.total_pages == 4

    def test_total_pages_calculation_with_remainder(self):
        """Test total_pages calculation with remainder."""
        items = list(range(1, 98))  # 97 items
        response = paginate(items, page=1, page_size=25)
        assert response.total_pages == 4  # 97 / 25 = 3.88, rounds up to 4
