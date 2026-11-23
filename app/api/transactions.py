from datetime import date

from fastapi import APIRouter, Query, status

from app.api.dependencies import DbSession
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.schema import ApiResponse
from app.transactions.model import TransactionState, TransactionType
from app.transactions.schema import SeedData, SeedRequest, TransactionPage
from app.transactions.service import create_transactions, list_transactions

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/seed", response_model=ApiResponse[SeedData], status_code=status.HTTP_201_CREATED)
def seed_transactions(request: SeedRequest, db: DbSession) -> ApiResponse[SeedData]:
    """
    Seed transactions in the database.
    """
    return ApiResponse[SeedData](
        success=True,
        message="Transactions seeded successfully",
        data=create_transactions(db, request)
    )


@router.get("", response_model=ApiResponse[TransactionPage])
def get_transactions(
    db: DbSession,
    day: date,                                                          # Kathmandu calendar day, e.g. 2026-11-20
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    type: TransactionType | None = None,                                # optional filter
    state: TransactionState | None = None,                              # optional filter
) -> ApiResponse[TransactionPage]:
    """
    List one day's transactions, newest first, a page at a time.
    """
    return ApiResponse[TransactionPage](
        success=True,
        message="Transactions fetched successfully",
        data=list_transactions(db, day, page, page_size, type, state),
    )
