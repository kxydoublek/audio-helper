import json
import uuid
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


class AudioRecordNotFound(Exception):
    pass


class AudioRecordExpired(Exception):
    pass


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_upload_audio(audio_id: str) -> tuple[bytes, dict[str, Any]]:
    try:
        uuid.UUID(audio_id)
    except ValueError as exc:
        raise AudioRecordNotFound from exc

    meta_path = AUDIO_DIR / f"{audio_id}.json"
    audio_path = AUDIO_DIR / f"{audio_id}.webm"
    if not meta_path.is_file() or not audio_path.is_file():
        raise AudioRecordNotFound

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioRecordNotFound from exc
    if not isinstance(metadata, dict):
        raise AudioRecordNotFound

    expires_at = _parse_dt(metadata.get("expires_at"))
    if expires_at is None:
        created_at = _parse_dt(metadata.get("created_at"))
        if created_at is not None:
            expires_at = created_at + timedelta(hours=settings.audio_ttl_hours)
    if expires_at is not None and _utcnow() >= expires_at:
        raise AudioRecordExpired

    try:
        payload = audio_path.read_bytes()
    except OSError as exc:
        raise AudioRecordNotFound from exc
    if not payload:
        raise AudioRecordNotFound
    return payload, metadata
