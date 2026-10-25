"""Library validation and borrower-record authorization regressions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.library.schemas.library import AddCopiesRequest, BookCreate, BookUpdate, LendingPolicyUpdate, ReturnBookRequest
from shared.database.base import get_db


@pytest.mark.parametrize("isbn,normalized", [("978-0-306-40615-7", "9780306406157"), ("0-306-40615-2", "0306406152"), ("", None)])
def test_library_isbn_normalizes_and_checks_the_checksum(isbn, normalized):
    assert BookCreate(title="Test", author="Author", isbn=isbn).isbn == normalized


@pytest.mark.parametrize("isbn", ["9780306406158", "0306406153", "not-an-isbn"])
def test_library_rejects_invalid_isbn(isbn):
    with pytest.raises(ValidationError, match="valid ISBN"):
        BookCreate(title="Test", author="Author", isbn=isbn)


def test_reference_titles_default_to_in_library_use():
    assert BookCreate(title="Reference", author="Author", category="reference").is_lendable is False
    assert BookCreate(title="Reference", author="Author", category="reference", is_lendable=True).is_lendable is True


def test_empty_catalog_names_and_null_required_updates_are_rejected():
    with pytest.raises(ValidationError):
        BookCreate(title="   ", author="Author")
    with pytest.raises(ValidationError):
        BookUpdate(title=None)


def test_accessions_are_distinct_and_count_matches_stock():
    with pytest.raises(ValidationError, match="distinct"):
        AddCopiesRequest(count=2, accession_numbers=["ACC-1", " acc-1 "])
    assert AddCopiesRequest(count=1, accession_numbers=[" पुस्-०१ "]).accession_numbers == ["पुस्-०१"]


def test_policy_fines_require_a_cap_and_damage_requires_a_reason():
    with pytest.raises(ValidationError, match="fine cap"):
        LendingPolicyUpdate(daily_fine="1.00")
    with pytest.raises(ValidationError, match="reason"):
        ReturnBookRequest(book_issue_id=uuid4(), condition="damaged")
    with pytest.raises(ValidationError):
        ReturnBookRequest(book_issue_id=uuid4(), fine_amount="0.001")


@pytest.mark.asyncio
@pytest.mark.parametrize("reader_role", ["parent", "student"])
async def test_catalog_permission_does_not_expose_private_borrower_registers(reader_role):
    db = AsyncMock()
    async def session():
        yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=uuid4(), school_id=uuid4(), full_name_en="Reader",
        has_role=lambda role: role == reader_role, has_permission=lambda code: code == "library:read",
    )
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for path in ["issued", "borrowers", "stats", "history", "policy", "export?report=loans"]:
                response = await client.get(f"/api/v1/library/{path}")
                assert response.status_code == 403, path
        db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
