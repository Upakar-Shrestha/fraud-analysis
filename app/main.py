from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import settings
from app.core.constants import APP_TITLE
from app.core.logging import configure_logging
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
app.include_router(api_router) 