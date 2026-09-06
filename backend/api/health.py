from fastapi import APIRouter, Request

from http_util import get_request_id
from schemas import HealthData, SuccessResponse

router = APIRouter()


@router.get("/health", response_model=SuccessResponse[HealthData])
def health(request: Request) -> SuccessResponse[HealthData]:
    return SuccessResponse(
        request_id=get_request_id(request),
        data=HealthData(status="ok"),
    )
