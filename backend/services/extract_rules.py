from typing import NoReturn

from pydantic import BaseModel, ConfigDict, ValidationError

from errors import AppError
from schemas import ExtractData

STAGE = "extract"
VAGUE_ADDRESSES = {
    "我家",
    "公司",
    "学校",
    "这边",
    "那里",
    "我家门口",
    "公司楼下",
}
CATEGORY_ALIASES = {
    "喝咖啡": "咖啡店",
    "来杯咖啡": "咖啡店",
    "咖啡": "咖啡店",
    "咖啡馆": "咖啡店",
}


class ExtractModelOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city_a: str | None
    address_a: str | None
    city_b: str | None
    address_b: str | None
    category: str | None
    party_count: int | None
    incomplete_reason: str | None


def _fail(status_code: int, code: str, message: str, reason: str | None = None) -> NoReturn:
    raise AppError(
        status_code=status_code,
        code=code,
        message=message,
        stage=STAGE,
        reason=reason,
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def normalize_city(value: str | None) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if text.endswith("市") and len(text) > 1:
        return text[:-1]
    return text


def normalize_category(value: str | None) -> str:
    text = _clean(value)
    if text is None:
        return "咖啡店"
    return CATEGORY_ALIASES.get(text, text)


def normalize_address(value: str | None) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    if text in VAGUE_ADDRESSES:
        return None
    return text


def parse_model_output(payload: object) -> ExtractModelOutput:
    if not isinstance(payload, dict):
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="payload is not an object",
        )
    try:
        return ExtractModelOutput.model_validate(payload)
    except ValidationError:
        _fail(
            502,
            "EXTRACT_MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            reason="pydantic validation failed",
        )


def to_business_result(model: ExtractModelOutput) -> ExtractData:
    if model.party_count != 2:
        _fail(
            422,
            "EXTRACT_PARTY_COUNT",
            "目前只支持两个人找中间点，请重新说你们两个人的位置。",
            reason=f"party_count={model.party_count}",
        )

    city_a = normalize_city(model.city_a)
    city_b = normalize_city(model.city_b)
    address_a = normalize_address(model.address_a)
    address_b = normalize_address(model.address_b)
    category = normalize_category(model.category)

    if city_a is None or address_a is None or city_b is None or address_b is None:
        _fail(
            422,
            "EXTRACT_INCOMPLETE",
            "没有听清双方的具体地点。请说出可定位的地名，不要只说「我家」或「公司」。",
            reason=model.incomplete_reason or "missing city or address",
        )

    if city_a != city_b:
        _fail(
            422,
            "EXTRACT_CROSS_CITY",
            "目前只支持同一座城市内的两个人，请重新说一次双方地点。",
            reason=f"{city_a} vs {city_b}",
        )

    return ExtractData(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=category,
    )
