import base64
import logging
import re
from typing import NoReturn

import httpx

from audio_limits import ASR_TIMEOUT_SECONDS, MAX_ASR_INPUT_BYTES
from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "asr"
_EMPTY_TEXT = re.compile(r"[\s\.,，。！？、!?;；:：'\"“”‘’…—\-·]+")


def _fail(status_code: int, code: str, message: str, reason: str | None = None) -> NoReturn:
    raise AppError(
        status_code=status_code,
        code=code,
        message=message,
        stage=STAGE,
        reason=reason,
    )


def _is_blank_transcript(text: str) -> bool:
    return _EMPTY_TEXT.sub("", text) == ""


def _media_type(mime: str | None) -> str:
    raw = (mime or "audio/webm").split(";", 1)[0].strip().lower()
    return raw or "audio/webm"


def _extract_text(payload: object) -> str:
    if not isinstance(payload, dict):
        _fail(
            502,
            "ASR_MODEL_OUTPUT_INVALID",
            "语音识别结果格式异常，请稍后重试。",
            reason="response is not an object",
        )
    if payload.get("error") and not payload.get("choices"):
        _fail(
            502,
            "ASR_UPSTREAM_ERROR",
            "语音识别服务暂时不可用，请稍后重试。",
            reason="upstream error object",
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        _fail(
            502,
            "ASR_MODEL_OUTPUT_INVALID",
            "语音识别结果格式异常，请稍后重试。",
            reason="missing choices",
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        _fail(
            502,
            "ASR_MODEL_OUTPUT_INVALID",
            "语音识别结果格式异常，请稍后重试。",
            reason="missing message",
        )
    text = message.get("content")
    if text is None:
        return ""
    if not isinstance(text, str):
        _fail(
            502,
            "ASR_MODEL_OUTPUT_INVALID",
            "语音识别结果格式异常，请稍后重试。",
            reason="content is not a string",
        )
    return text.strip()


async def recognize(audio_bytes: bytes, mime: str | None) -> str:
    api_key = settings.bailian_api_key.strip()
    if not api_key:
        _fail(
            502,
            "ASR_UPSTREAM_ERROR",
            "语音识别服务暂不可用，请稍后重试。",
            reason="missing api key",
        )

    media_type = _media_type(mime)
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    data_uri = f"data:{media_type};base64,{encoded}"
    if len(data_uri.encode("utf-8")) > MAX_ASR_INPUT_BYTES:
        _fail(
            413,
            "AUDIO_BASE64_TOO_LARGE",
            "录音编码后体积过大，请缩短录音后重试。",
            reason="encoded data url exceeds 10MB",
        )

    body = {
        "model": settings.bailian_asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": data_uri},
                    }
                ],
            }
        ],
        "stream": False,
        "asr_options": {
            "language": "zh",
            "enable_itn": True,
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=ASR_TIMEOUT_SECONDS) as client:
            response = await client.post(
                settings.bailian_asr_url,
                json=body,
                headers=headers,
            )
    except httpx.TimeoutException:
        logger.info("stage=%s error=%s reason=timeout", STAGE, "ASR_UPSTREAM_TIMEOUT")
        _fail(
            504,
            "ASR_UPSTREAM_TIMEOUT",
            "语音识别超时，请稍后重试。",
            reason="httpx timeout",
        )
    except httpx.HTTPError as exc:
        logger.info("stage=%s error=%s reason=%s", STAGE, "ASR_UPSTREAM_ERROR", type(exc).__name__)
        _fail(
            502,
            "ASR_UPSTREAM_ERROR",
            "语音识别服务暂时不可用，请稍后重试。",
            reason=type(exc).__name__,
        )

    logger.info("stage=%s upstream_status=%s", STAGE, response.status_code)
    if response.status_code >= 500:
        _fail(
            502,
            "ASR_UPSTREAM_ERROR",
            "语音识别服务暂时不可用，请稍后重试。",
            reason=f"http_{response.status_code}",
        )
    if response.status_code != 200:
        _fail(
            502,
            "ASR_UPSTREAM_ERROR",
            "语音识别服务暂时不可用，请稍后重试。",
            reason=f"http_{response.status_code}",
        )

    try:
        payload = response.json()
    except ValueError:
        _fail(
            502,
            "ASR_MODEL_OUTPUT_INVALID",
            "语音识别结果格式异常，请稍后重试。",
            reason="response is not json",
        )

    text = _extract_text(payload)
    if _is_blank_transcript(text):
        _fail(
            422,
            "ASR_EMPTY_TEXT",
            "没有听清你说的内容，请靠近麦克风后重新说一次。",
            reason="empty transcript",
        )
    return text
