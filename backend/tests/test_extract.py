import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from config import settings
from errors import AppError
from main import app
from services.extract_rules import parse_model_output, to_business_result


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    with TestClient(app) as test_client:
        yield test_client


def _model_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_extract_missing_field(client):
    response = client.post("/extract", json={"text": "我在杭州东站"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "extract"


@respx.mock
def test_extract_success_returns_five_fields(client):
    respx.post(settings.deepseek_url).mock(
        return_value=_model_response(
            '{"city_a":"杭州","address_a":"杭州东站","city_b":"杭州市","address_b":"西湖龙翔桥地铁站","category":"喝咖啡","party_count":2,"incomplete_reason":null}'
        )
    )
    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间喝咖啡。",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
    }
    assert "party_count" not in data


@respx.mock
def test_extract_incomplete_home(client):
    respx.post(settings.deepseek_url).mock(
        return_value=_model_response(
            '{"city_a":"杭州","address_a":null,"city_b":"杭州","address_b":"西湖","category":"咖啡店","party_count":2,"incomplete_reason":"缺少可定位的地址A"}'
        )
    )
    response = client.post(
        "/extract",
        json={"text": "我在公司，朋友在西湖，找个咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXTRACT_INCOMPLETE"


@respx.mock
def test_extract_party_count(client):
    respx.post(settings.deepseek_url).mock(
        return_value=_model_response(
            '{"city_a":"杭州","address_a":"杭州东站","city_b":null,"address_b":null,"category":"咖啡店","party_count":3,"incomplete_reason":"人数不是2人"}'
        )
    )
    response = client.post(
        "/extract",
        json={
            "text": "我、小王和小李分别在杭州东站、城西银泰和龙翔桥，找个中间的咖啡店。",
            "city": "杭州",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXTRACT_PARTY_COUNT"


@respx.mock
def test_extract_cross_city(client):
    respx.post(settings.deepseek_url).mock(
        return_value=_model_response(
            '{"city_a":"杭州","address_a":"杭州东站","city_b":"上海","address_b":"虹桥站","category":"咖啡店","party_count":2,"incomplete_reason":null}'
        )
    )
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在上海虹桥站，找个咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXTRACT_CROSS_CITY"


@respx.mock
def test_extract_invalid_json(client):
    respx.post(settings.deepseek_url).mock(
        return_value=_model_response("not-json")
    )
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在龙翔桥。", "city": "杭州"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "EXTRACT_MODEL_OUTPUT_INVALID"


def test_vague_address_is_incomplete():
    model = parse_model_output(
        {
            "city_a": "杭州",
            "address_a": "我家",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
            "party_count": 2,
            "incomplete_reason": "无法定位的地点",
        }
    )
    with pytest.raises(AppError) as exc:
        to_business_result(model)
    assert exc.value.code == "EXTRACT_INCOMPLETE"
