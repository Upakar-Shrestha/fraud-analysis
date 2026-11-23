import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.transactions.model import TransactionChannel, TransactionState, TransactionType


class SeedRequest(BaseModel):
    seed: int = Field(ge=0)
    end_date: date

class SeedData(BaseModel):
    inserted: int
    skipped: int
    total_generated: int
    fraud_count: int


class TransactionRead(BaseModel):
    # lets Pydantic read values straight from a SQLAlchemy Transaction object
    model_config = ConfigDict(from_attributes=True)

    idx: uuid.UUID
    created_on: datetime
    type: TransactionType
    state: TransactionState
    amount: int                                     # paisa
    source_user_id: str | None
    source_account_created_on: datetime | None
    destination_user_id: str | None
    external_account: str | None
    device_id: str | None
    channel: TransactionChannel
    parent_txn: uuid.UUID | None
    remarks: str | None
    # is_synthetic_fraud left out on purpose: ground truth is for evaluation only


class TransactionPage(BaseModel):
    items: list[TransactionRead]
    page: int
    page_size: int
    total: int                                      # rows matching the filters, across all pages
