import logging
import time
import uuid

from fastapi import APIRouter, File, Request, UploadFile

from audio_limits import (
    DURATION_UPPER_SLACK_SECONDS,
    MAX_AUDIO_BYTES,
    MAX_AUDIO_SECONDS,
    MIN_AUDIO_SECONDS,
)
from errors import AppError
from http_util import get_request_id
from schemas import SuccessResponse, UploadData
from services.audio_probe import ProbeFormatError, ProbeUnavailableError, probe_webm_opus
from services.audio_store import (
    delete_upload_audio,
    finalize_upload_audio,
    write_upload_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "upload"


def _fail(status_code: int, code: str, message: str, reason: str | None = None) -> None:
    raise AppError(
        status_code=status_code,
        code=code,
        message=message,
        stage=STAGE,
        reason=reason,
    )


async def _read_limited(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_AUDIO_BYTES:
            _fail(
                413,
                "AUDIO_TOO_LARGE",
                "录音文件不能超过 5MB，请缩短录音后重试。",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=SuccessResponse[UploadData])
async def upload(
    request: Request,
    file: UploadFile = File(...),
) -> SuccessResponse[UploadData]:
    started = time.perf_counter()
    request_id = get_request_id(request)
    audio_id = str(uuid.uuid4())
    payload = await _read_limited(file)

    if not payload:
        _fail(
            415,
            "AUDIO_UNSUPPORTED_FORMAT",
            "录音格式不受支持。请使用能录制 WebM/Opus 的浏览器。",
            reason="empty file",
        )

    try:
        audio_path = write_upload_payload(audio_id, payload)
        probe = probe_webm_opus(audio_path)
        duration = probe.duration_seconds
        if duration is None:
            delete_upload_audio(audio_id)
            _fail(
                422,
                "AUDIO_DURATION_UNKNOWN",
                "无法确认录音时长，请换浏览器重试。",
                reason="no duration from format/stream/packets",
            )
        if duration < MIN_AUDIO_SECONDS or duration > (
            MAX_AUDIO_SECONDS + DURATION_UPPER_SLACK_SECONDS
        ):
            delete_upload_audio(audio_id)
            _fail(
                422,
                "AUDIO_DURATION_INVALID",
                "请将录音控制在 1 到 60 秒。",
                reason=f"duration_seconds={duration}",
            )

        stored_duration = min(duration, MAX_AUDIO_SECONDS)
        finalize_upload_audio(
            audio_id,
            mime="audio/webm",
            codec=probe.codec_name,
            duration_seconds=stored_duration,
            duration_source=probe.duration_source,
            size_bytes=len(payload),
        )
    except AppError:
        raise
    except ProbeUnavailableError as exc:
        delete_upload_audio(audio_id)
        logger.info(
            "stage=%s request_id=%s error=%s reason=%s elapsed_ms=%s",
            STAGE,
            request_id,
            "AUDIO_PROBE_UNAVAILABLE",
            str(exc),
            int((time.perf_counter() - started) * 1000),
        )
        _fail(
            500,
            "AUDIO_PROBE_UNAVAILABLE",
            "暂时无法校验录音，请稍后重试。",
            reason=str(exc),
        )
    except ProbeFormatError as exc:
        delete_upload_audio(audio_id)
        _fail(
            415,
            "AUDIO_UNSUPPORTED_FORMAT",
            "录音格式不受支持。请使用能录制 WebM/Opus 的浏览器。",
            reason=str(exc),
        )
    except Exception:
        delete_upload_audio(audio_id)
        logger.exception(
            "stage=%s request_id=%s error=%s elapsed_ms=%s",
            STAGE,
            request_id,
            "INTERNAL_ERROR",
            int((time.perf_counter() - started) * 1000),
        )
        _fail(
            500,
            "INTERNAL_ERROR",
            "暂时无法校验录音，请稍后重试。",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "stage=%s request_id=%s audio_id=%s duration_s=%s elapsed_ms=%s",
        STAGE,
        request_id,
        audio_id,
        stored_duration,
        elapsed_ms,
    )
    return SuccessResponse(
        request_id=request_id,
        data=UploadData(audio_id=audio_id),
    )
