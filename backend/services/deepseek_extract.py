import json
import logging
from typing import NoReturn

import httpx

from audio_limits import EXTRACT_MAX_TOKENS, EXTRACT_TIMEOUT_SECONDS
from config import BACKEND_DIR, settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "extract"
PROMPT_PATH = BACKEND_DIR / "prompts" / "extract.txt"


def _fail(status_code: int, code: str, message: str, reason: str | None = None) -> NoReturn:
    raise AppError(
        status_code=status_code,
        code=code,
        message=message,
        stage=STAGE,
        reason=reason,
    )


def load_extract_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.info("stage=%s error=%s reason=prompt missing", STAGE, "INTERNAL_ERROR")
        _fail(
            500,
            "INTERNAL_ERROR",
            "地点信息整理失败，请稍后重试。",
            reason="extract prompt file missing",
        )


def _parse_json_content(content: object) -> object:
    if not isinstance(content, str) or not content.strip():
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="empty model content",
        )
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="content is not json",
        )


async def complete_extract_json(page_city: str, text: str) -> object:
    api_key = settings.deepseek_api_key.strip()
    if not api_key:
        _fail(
            502,
            "EXTRACT_UPSTREAM_ERROR",
            "地点信息整理失败，请稍后重试。",
            reason="missing api key",
        )

    body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": load_extract_prompt()},
            {
                "role": "user",
                "content": f"page_city: {page_city.strip()}\ntext: {text.strip()}",
            },
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": EXTRACT_MAX_TOKENS,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=EXTRACT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                settings.deepseek_url,
                json=body,
                headers=headers,
            )
    except httpx.TimeoutException:
        logger.warning("stage=%s error=%s reason=timeout", STAGE, "EXTRACT_UPSTREAM_TIMEOUT")
        _fail(
            504,
            "EXTRACT_UPSTREAM_TIMEOUT",
            "地点信息整理超时，请稍后重试。",
            reason="httpx timeout",
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "stage=%s error=%s reason=%s",
            STAGE,
            "EXTRACT_UPSTREAM_ERROR",
            type(exc).__name__,
        )
        _fail(
            502,
            "EXTRACT_UPSTREAM_ERROR",
            "地点信息整理失败，请稍后重试。",
            reason=type(exc).__name__,
        )

    logger.warning("stage=%s upstream_status=%s", STAGE, response.status_code)
    if response.status_code in {401, 403}:
        _fail(
            502,
            "EXTRACT_UPSTREAM_ERROR",
            "DeepSeek 鉴权失败，请确认 DEEPSEEK_API_KEY 是官网 API Key（一般以 sk- 开头），并重启后端。",
            reason=f"http_{response.status_code}",
        )
    if response.status_code != 200:
        _fail(
            502,
            "EXTRACT_UPSTREAM_ERROR",
            "地点信息整理失败，请稍后重试。",
            reason=f"http_{response.status_code}",
        )

    try:
        payload = response.json()
    except ValueError:
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="response is not json",
        )

    if not isinstance(payload, dict):
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="response is not an object",
        )
    if payload.get("error") and not payload.get("choices"):
        _fail(
            502,
            "EXTRACT_UPSTREAM_ERROR",
            "地点信息整理失败，请稍后重试。",
            reason="upstream error object",
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="missing choices",
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="missing message",
        )
    return _parse_json_content(message.get("content"))
