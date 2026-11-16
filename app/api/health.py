from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.core.schema import ApiResponse
from app.health.schema import HealthData
from app.health.service import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse[HealthData])
def get_health(session: DbSession) -> ApiResponse[HealthData]:
    return ApiResponse[HealthData](
        success=True,
        message="Service is healthy",
        data=check_database(session),
    )
