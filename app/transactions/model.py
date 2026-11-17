import datetime
import uuid
import enum

from sqlalchemy import UUID, BigInteger, Boolean, CheckConstraint, DateTime, Enum, Index, func, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class TransactionStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class TransactionType(str, enum.Enum):
    TOPUP = "TOPUP"                        
    P2P_TRANSFER = "P2P_TRANSFER"          
    MERCHANT_PAYMENT = "MERCHANT_PAYMENT"  
    BILL_PAYMENT = "BILL_PAYMENT"          
    BANK_WITHDRAWAL = "BANK_WITHDRAWAL"

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"))
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus, name="transaction_status"))
    sender_wallet_id: Mapped[str | None] = mapped_column(String(64))                            # null for TOPUP
    receiver_wallet_id: Mapped[str | None] = mapped_column(String(64))                          # null for external receivers
    amount: Mapped[int] = mapped_column(BigInteger)                                             # paisa, never float
    device_id: Mapped[str] = mapped_column(String(64))                                          # device id of the wallet that initiated transaction
    transaction_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))                   
    is_synthetic_fraud: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))     # for evaluation
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "sender_wallet_id IS NOT NULL OR receiver_wallet_id IS NOT NULL",
            name="ck_transactions_has_wallet",
        ),
        Index("ix_transactions_sender_transaction_at", "sender_wallet_id", "transaction_at"),
        Index("ix_transactions_receiver_transaction_at", "receiver_wallet_id", "transaction_at"),
        Index("ix_transactions_transaction_at", "transaction_at"),
    )