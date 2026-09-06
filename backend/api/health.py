import uuid

from fastapi import APIRouter

from schemas import HealthData, SuccessResponse

router = APIRouter()


@router.get("/health", response_model=SuccessResponse[HealthData])
def health() -> SuccessResponse[HealthData]:
    return SuccessResponse(
        request_id=str(uuid.uuid4()),
        data=HealthData(status="ok"),
    )
