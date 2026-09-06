import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import BACKEND_DIR, settings

AUDIO_DIR = BACKEND_DIR / "storage" / "audio"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def write_upload_payload(audio_id: str, payload: bytes) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = AUDIO_DIR / f"{audio_id}.part"
    temp_path.write_bytes(payload)
    return temp_path


def finalize_upload_audio(
    audio_id: str,
    *,
    mime: str,
    codec: str,
    duration_seconds: float,
    duration_source: str | None,
    size_bytes: int,
) -> None:
    audio_path = AUDIO_DIR / f"{audio_id}.webm"
    temp_path = AUDIO_DIR / f"{audio_id}.part"
    meta_path = AUDIO_DIR / f"{audio_id}.json"
    created_at = _utcnow()
    expires_at = created_at + timedelta(hours=settings.audio_ttl_hours)
    metadata: dict[str, Any] = {
        "audio_id": audio_id,
        "kind": "upload",
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "mime": mime,
        "codec": codec,
        "duration_seconds": duration_seconds,
        "duration_source": duration_source,
        "size_bytes": size_bytes,
    }
    try:
        if temp_path.exists():
            temp_path.replace(audio_path)
        meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        delete_upload_audio(audio_id)
        raise


def delete_upload_audio(audio_id: str) -> None:
    for suffix in (".webm", ".json", ".part"):
        path = AUDIO_DIR / f"{audio_id}{suffix}"
        if path.exists():
            path.unlink()
