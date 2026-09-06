import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from config import settings
from main import app
from services import audio_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_store, "AUDIO_DIR", tmp_path)
    monkeypatch.setattr(settings, "bailian_api_key", "test-key")
    with TestClient(app) as test_client:
        yield test_client


def _write_audio(tmp_path, *, expired=False):
    audio_id = str(uuid4())
    created = datetime.now(timezone.utc)
    expires = created - timedelta(hours=1) if expired else created + timedelta(hours=24)
    (tmp_path / f"{audio_id}.webm").write_bytes(b"fake-webm-bytes")
    (tmp_path / f"{audio_id}.json").write_text(
        json.dumps(
            {
                "audio_id": audio_id,
                "kind": "upload",
                "created_at": created.isoformat(),
                "expires_at": expires.isoformat(),
                "mime": "audio/webm",
                "codec": "opus",
                "duration_seconds": 3.0,
                "duration_source": "packets",
                "size_bytes": 15,
            }
        ),
        encoding="utf-8",
    )
    return audio_id


def test_asr_missing_field(client):
    response = client.post("/asr", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"


def test_asr_unknown_id(client):
    response = client.post("/asr", json={"audio_id": str(uuid4())})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AUDIO_ID_NOT_FOUND"
    assert body["error"]["stage"] == "asr"


def test_asr_expired_id(client, tmp_path):
    audio_id = _write_audio(tmp_path, expired=True)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_ID_NOT_FOUND"


@respx.mock
def test_asr_success_mocked(client, tmp_path):
    audio_id = _write_audio(tmp_path)
    respx.post(settings.bailian_asr_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "我在杭州东站，朋友在西湖龙翔桥地铁站。"
                        }
                    }
                ]
            },
        )
    )
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 200
    body = response.json()
    assert "request_id" in body
    assert body["data"]["text"] == "我在杭州东站，朋友在西湖龙翔桥地铁站。"


@respx.mock
def test_asr_empty_text_mocked(client, tmp_path):
    audio_id = _write_audio(tmp_path)
    respx.post(settings.bailian_asr_url).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "。"}}]},
        )
    )
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ASR_EMPTY_TEXT"


@respx.mock
def test_asr_timeout_mocked(client, tmp_path):
    audio_id = _write_audio(tmp_path)
    respx.post(settings.bailian_asr_url).mock(side_effect=httpx.TimeoutException("timeout"))
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "ASR_UPSTREAM_TIMEOUT"


def test_asr_missing_key_mocked(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "bailian_api_key", "")
    audio_id = _write_audio(tmp_path)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ASR_UPSTREAM_ERROR"


@respx.mock
def test_asr_upstream_error_mocked(client, tmp_path):
    audio_id = _write_audio(tmp_path)
    respx.post(settings.bailian_asr_url).mock(return_value=httpx.Response(500, json={}))
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ASR_UPSTREAM_ERROR"
