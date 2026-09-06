import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from api.health import router as health_router
from api.upload import router as upload_router
from config import settings
from errors import AppError
from http_util import get_request_id, stage_for_path
from schemas import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="语音约碰面地点", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    stage: str,
) -> JSONResponse:
    body = ErrorResponse(
        request_id=get_request_id(request),
        error=ErrorDetail(code=code, message=message, stage=stage),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    logger.info(
        "stage=%s request_id=%s error=%s reason=%s",
        exc.stage,
        get_request_id(request),
        exc.code,
        exc.reason or "",
    )
    return _error_response(
        request,
        exc.status_code,
        exc.code,
        exc.message,
        exc.stage,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        request,
        422,
        "VALIDATION_ERROR",
        "请求缺少文件或字段类型不正确。",
        stage_for_path(request.url.path),
    )


app.include_router(health_router)
app.include_router(upload_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
