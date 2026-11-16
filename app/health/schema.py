from pydantic import BaseModel


class HealthData(BaseModel):
    database: str
