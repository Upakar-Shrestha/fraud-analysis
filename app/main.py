from contextlib import asynccontextmanager

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import settings
from app.core.constants import APP_TITLE
from app.core.logging import configure_logging
from app.exceptions.base import AppError  
from app.exceptions.handlers import (  
    handle_app_error,
    handle_http_error,
    handle_unexpected_error,
    handle_validation_error,
)
from app.infrastructure.database import engine


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs once before the app accepts requests
    configure_logging(settings.LOG_LEVEL)
    logger.info("app_started", log_level=settings.LOG_LEVEL)
    yield  
    # close all pooled DB connections cleanly
    engine.dispose()
    logger.info("app_stopped")


app = FastAPI(title=APP_TITLE, lifespan=lifespan)   

app.add_exception_handler(AppError, handle_app_error)  
app.add_exception_handler(RequestValidationError, handle_validation_error)  
app.add_exception_handler(StarletteHTTPException, handle_http_error)  
app.add_exception_handler(Exception, handle_unexpected_error)

app.include_router(api_router) 