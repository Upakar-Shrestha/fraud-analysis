"""update transaction schema

Revision ID: e0f86051814b
Revises: 3381ca65b411
Create Date: 2026-11-20 16:13:11.080735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# create_type=False: we create these types ourselves in upgrade(); create_table's
# automatic creation skips a type name it already created earlier in the same run
transaction_type = postgresql.ENUM("LOAD", "TRANSFER", "PAYMENT", "WITHDRAW", "CASH_IN", "CASH_OUT", "REFUND", "REWARD", name="transaction_type", create_type=False)
transaction_state = postgresql.ENUM("INITIATED", "PENDING", "ON_HOLD", "COMPLETED", "FAILED", "REFUNDED", "CANCELED", name="transaction_state", create_type=False)
transaction_channel = postgresql.ENUM("APP", "WEB", "QR", "MERCHANT_API", "AGENT_TERMINAL", name="transaction_channel", create_type=False)

# revision identifiers, used by Alembic.
revision: str = 'e0f86051814b'
down_revision: Union[str, Sequence[str], None] = '3381ca65b411'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # old table holds only synthetic seed data, so drop and recreate instead of altering every column
    op.drop_table("transactions")  # also drops its indexes
    # enum types survive drop_table; drop them so the new transaction_type can be created with new values
    sa.Enum(name="transaction_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transaction_type").drop(op.get_bind(), checkfirst=True)
    transaction_type.create(op.get_bind())
    transaction_state.create(op.get_bind())
    transaction_channel.create(op.get_bind())

    op.create_table(
        "transactions",
        sa.Column("idx", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_on", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("state", transaction_state, nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("source_user_id", sa.String(length=64), nullable=True),
        sa.Column("source_account_created_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destination_user_id", sa.String(length=64), nullable=True),
        sa.Column("external_account", sa.String(length=64), nullable=True),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("channel", transaction_channel, nullable=False),
        sa.Column("parent_txn", sa.UUID(), nullable=True),
        sa.Column("remarks", sa.String(length=255), nullable=True),
        sa.Column("is_synthetic_fraud", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("source_user_id IS NOT NULL OR destination_user_id IS NOT NULL", name="ck_transactions_has_user"),
        sa.ForeignKeyConstraint(["parent_txn"], ["transactions.idx"]),  # self-reference, e.g. REFUND -> original
        sa.PrimaryKeyConstraint("idx"),
    )
    op.create_index("ix_transactions_source_created_on", "transactions", ["source_user_id", "created_on"], unique=False)
    op.create_index("ix_transactions_destination_created_on", "transactions", ["destination_user_id", "created_on"], unique=False)
    op.create_index("ix_transactions_created_on", "transactions", ["created_on"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transactions")
    sa.Enum(name="transaction_channel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transaction_state").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transaction_type").drop(op.get_bind(), checkfirst=True)

    # recreate the table exactly as revision 3381ca65b411 left it
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("transaction_type", sa.Enum("TOPUP", "P2P_TRANSFER", "MERCHANT_PAYMENT", "BILL_PAYMENT", "BANK_WITHDRAWAL", name="transaction_type"), nullable=False),
        sa.Column("status", sa.Enum("INITIATED", "PENDING", "ON_HOLD", "COMPLETED", "FAILED", "REFUNDED", "CANCELLED", name="transaction_status"), nullable=False),
        sa.Column("sender_wallet_id", sa.String(length=64), nullable=True),
        sa.Column("receiver_wallet_id", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_synthetic_fraud", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("sender_wallet_id IS NOT NULL OR receiver_wallet_id IS NOT NULL", name="ck_transactions_has_wallet"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_receiver_transaction_at", "transactions", ["receiver_wallet_id", "transaction_at"], unique=False)
    op.create_index("ix_transactions_sender_transaction_at", "transactions", ["sender_wallet_id", "transaction_at"], unique=False)
    op.create_index("ix_transactions_transaction_at", "transactions", ["transaction_at"], unique=False)
