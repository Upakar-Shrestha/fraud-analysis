from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings
from app.core.constants import DB_MAX_OVERFLOW, DB_POOL_SIZE, DB_POOL_TIMEOUT_SECONDS

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    pool_pre_ping=True,
)

SessionFactory = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

