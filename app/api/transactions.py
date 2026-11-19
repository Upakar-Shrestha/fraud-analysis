from fastapi import APIRouter, status
from app.api.dependencies import DbSession
from app.transactions.schema import SeedData, SeedRequest
from app.core.schema import ApiResponse
from app.transactions.service import create_transactions

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
