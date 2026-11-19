from datetime import date
from pydantic import BaseModel, Field


class SeedRequest(BaseModel):
    seed: int = Field(ge=0)
    end_date: date  

class SeedData(BaseModel):
    inserted: int
    skipped: int
    total_generated: int
    fraud_count: int