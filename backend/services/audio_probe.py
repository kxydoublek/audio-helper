import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from audio_limits import PROBE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class ProbeUnavailableError(Exception):
    pass


class ProbeFormatError(Exception):
    pass


@dataclass
class ProbeResult:
    format_name: str
    codec_name: str
    duration_seconds: float | None
    duration_source: str | None


def _which_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise ProbeUnavailableError("ffprobe not found")
    return path


def _parse_duration(value: object) -> float | None:
    if value is None or isinstance(value, (list, dict)):
        return None
    text = str(value).strip()
    if text == "" or text.upper() == "N/A":
        return None
    try:
        duration = float(text)
    except ValueError:
        return None
    if duration < 0 or duration == float("inf"):
        return None
    return duration


def _run_ffprobe(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    executable = _which_ffprobe()
    try:
        return subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeFormatError("ffprobe timed out") from exc


def _probe_container(path: Path, timeout: float) -> dict:
    completed = _run_ffprobe(
        [
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=timeout,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        logger.info(
            "ffprobe container failed returncode=%s",
            completed.returncode,
        )
        raise ProbeFormatError("ffprobe could not read container")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeFormatError("ffprobe returned invalid json") from exc
    if not isinstance(payload, dict):
        raise ProbeFormatError("ffprobe returned invalid json")
    return payload


def _duration_from_packets(path: Path, timeout: float) -> float | None:
    completed = _run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-of",
            "csv=p=0",
            str(path),
        ],
        timeout=timeout,
    )
    if completed.returncode != 0:
        logger.info("ffprobe packets failed returncode=%s", completed.returncode)
        return None

    last = None
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        pts = _parse_duration(parts[0] if parts else None)
        packet_duration = _parse_duration(parts[1] if len(parts) > 1 else None) or 0.0
        if pts is None:
            continue
        last = pts + packet_duration
    return last


def probe_webm_opus(path: Path) -> ProbeResult:
    remaining = PROBE_TIMEOUT_SECONDS
    payload = _probe_container(path, timeout=min(3.0, remaining))
    remaining = max(1.0, remaining - 3.0)

    format_info = payload.get("format") or {}
    format_name = str(format_info.get("format_name") or "")
    normalized_format = format_name.lower()
    if "webm" not in normalized_format and "matroska" not in normalized_format:
        raise ProbeFormatError("unsupported container")

    streams = payload.get("streams") or []
    audio_stream = None
    for stream in streams:
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break
    if not audio_stream:
        raise ProbeFormatError("no audio stream")

    codec_name = str(audio_stream.get("codec_name") or "").lower()
    if codec_name != "opus":
        raise ProbeFormatError("unsupported codec")

    duration = _parse_duration(format_info.get("duration"))
    source = "format" if duration is not None else None
    if duration is None:
        duration = _parse_duration(audio_stream.get("duration"))
        source = "stream" if duration is not None else None
    if duration is None:
        duration = _duration_from_packets(path, timeout=remaining)
        source = "packets" if duration is not None else None

    return ProbeResult(
        format_name=format_name,
        codec_name=codec_name,
        duration_seconds=duration,
        duration_source=source,
    )
