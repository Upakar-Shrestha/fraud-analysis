import datetime
import uuid
import enum

from sqlalchemy import UUID, BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, func, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class TransactionState(str, enum.Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"

class TransactionType(str, enum.Enum):
    LOAD = "LOAD"                        
    TRANSFER = "TRANSFER"          
    PAYMENT = "PAYMENT"  
    WITHDRAW = "WITHDRAW"          
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    REFUND = "REFUND"
    REWARD = "REWARD"

class TransactionChannel(str, enum.Enum):
    APP = "APP"
    WEB = "WEB"
    QR = "QR"
    MERCHANT_API = "MERCHANT_API"
    AGENT_TERMINAL = "AGENT_TERMINAL"

class Transaction(Base):
    __tablename__ = "transactions"

    idx: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    created_on: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())   # Transaction creation timestamp
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"))
    state: Mapped[TransactionState] = mapped_column(Enum(TransactionState, name="transaction_state"))
    amount: Mapped[int] = mapped_column(BigInteger)                                                             # Transaction amount stored in paisa
    source_user_id: Mapped[str | None] = mapped_column(String(64))                                              # Source or initiating user identifier
    source_account_created_on: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))       # where applicable
    destination_user_id: Mapped[str | None] = mapped_column(String(64))                                         # null when money leaves the wallet (e.g. WITHDRAW)
    external_account: Mapped[str | None] = mapped_column(String(64))                                            # masked bank/card id, never the full number
    device_id: Mapped[str | None] = mapped_column(String(64))                                                   # null for system-initiated REWARD/REFUND
    channel: Mapped[TransactionChannel] = mapped_column(Enum(TransactionChannel, name="transaction_channel"))
    parent_txn: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.idx"))   # e.g. REFUND -> original txn
    remarks: Mapped[str | None] = mapped_column(String(255))                                                    # Optional transaction description
    is_synthetic_fraud: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "source_user_id IS NOT NULL OR destination_user_id IS NOT NULL",
            name="ck_transactions_has_user",
        ),
        Index("ix_transactions_source_created_on", "source_user_id", "created_on"),
        Index("ix_transactions_destination_created_on", "destination_user_id", "created_on"),
        Index("ix_transactions_created_on", "created_on"),
    )