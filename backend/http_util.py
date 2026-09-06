import uuid

from fastapi import Request


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    return request_id


def stage_for_path(path: str) -> str:
    if path.rstrip("/").endswith("/upload"):
        return "upload"
    if path.rstrip("/").endswith("/health"):
        return "health"
    if path.rstrip("/").endswith("/asr"):
        return "asr"
    if path.rstrip("/").endswith("/extract"):
        return "extract"
    return "unknown"
