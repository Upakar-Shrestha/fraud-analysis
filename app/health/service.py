from sqlalchemy import text
from sqlalchemy.orm import Session

from app.health.schema import HealthData


def check_database(session: Session) -> HealthData:
    session.execute(text("SELECT 1"))
    return HealthData(database="ok")
