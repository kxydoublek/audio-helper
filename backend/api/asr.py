import logging
import time

from fastapi import APIRouter, Request

from errors import AppError
from http_util import get_request_id
from schemas import AsrData, AsrRequest, SuccessResponse
from services.audio_store import AudioRecordExpired, AudioRecordNotFound, load_upload_audio
from services.bailian_asr import recognize

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "asr"


def _fail(status_code: int, code: str, message: str, reason: str | None = None) -> None:
    raise AppError(
        status_code=status_code,
        code=code,
        message=message,
        stage=STAGE,
        reason=reason,
    )


@router.post("/asr", response_model=SuccessResponse[AsrData])
async def asr(request: Request, body: AsrRequest) -> SuccessResponse[AsrData]:
    started = time.perf_counter()
    request_id = get_request_id(request)

    try:
        audio_bytes, metadata = load_upload_audio(body.audio_id)
    except AudioRecordExpired:
        _fail(
            404,
            "AUDIO_ID_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            reason="expired",
        )
    except AudioRecordNotFound:
        _fail(
            404,
            "AUDIO_ID_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            reason="not found",
        )

    text = await recognize(audio_bytes, metadata.get("mime"))
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "stage=%s request_id=%s audio_id=%s text_len=%s elapsed_ms=%s",
        STAGE,
        request_id,
        body.audio_id,
        len(text),
        elapsed_ms,
    )
    return SuccessResponse(request_id=request_id, data=AsrData(text=text))
