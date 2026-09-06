import logging
import time

from fastapi import APIRouter, Request

from http_util import get_request_id
from schemas import ExtractData, ExtractRequest, SuccessResponse
from services.deepseek_extract import complete_extract_json
from services.extract_rules import parse_model_output, to_business_result

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "extract"


@router.post("/extract", response_model=SuccessResponse[ExtractData])
async def extract(request: Request, body: ExtractRequest) -> SuccessResponse[ExtractData]:
    started = time.perf_counter()
    request_id = get_request_id(request)
    raw = await complete_extract_json(body.city, body.text)
    model = parse_model_output(raw)
    result = to_business_result(model)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "stage=%s request_id=%s party_count=%s incomplete_reason=%s elapsed_ms=%s",
        STAGE,
        request_id,
        model.party_count,
        model.incomplete_reason,
        elapsed_ms,
    )
    return SuccessResponse(request_id=request_id, data=result)
