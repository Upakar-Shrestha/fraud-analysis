from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import structlog
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.schema import ApiResponse
from app.exceptions.base import AppError

logger = structlog.get_logger(__name__)

def build_error_response(status_code: int, message: str, headers: dict | None = None) -> JSONResponse:
    # one place that shapes every error into {success: false, message, data: null}
    body = ApiResponse[None](success=False, message=message).model_dump()
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return build_error_response(exc.status_code, exc.detail)


def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
    return build_error_response(422, message)


def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # routing 404 / 405; keep headers so 405 still sends "Allow"
    return build_error_response(exc.status_code, str(exc.detail), exc.headers)


def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # log the real error, never leak it to the client
    logger.exception("unhandled_error", path=request.url.path)
    return build_error_response(500, "Internal server error")