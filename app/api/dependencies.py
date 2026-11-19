from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.database import SessionFactory


def get_db_session(): 
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db_session)]
