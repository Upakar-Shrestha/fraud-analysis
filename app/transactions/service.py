from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import structlog

from app.core.constants import LOOKBACK_DAYS
from app.transactions.helper import day_window_utc, generate_transactions
from app.transactions.model import Transaction, TransactionState, TransactionType
from app.transactions.schema import SeedData, SeedRequest, TransactionPage, TransactionRead

logger = structlog.get_logger(__name__)

def create_transactions(db: Session, request: SeedRequest) -> SeedData:
    """
    Creates and inserts multiple transactions rows in the database.
    """
    rows = generate_transactions(request.seed, request.end_date)

    statement = (
        insert(Transaction)
        .on_conflict_do_nothing(index_elements=[Transaction.idx])
        .returning(Transaction.idx)
    )
    inserted = len(db.execute(statement, rows).all())
    db.commit()

    data=SeedData(
        inserted=inserted,
        skipped=len(rows) - inserted,
        total_generated=len(rows),
        fraud_count=sum(row["is_synthetic_fraud"] for row in rows),
    )
    logger.info("transactions_seeded", seed=request.seed)
    return data


def get_transactions_for_analysis(db: Session, day: date) -> pd.DataFrame:
    """
    Returns the target day's transactions plus the LOOKBACK_DAYS before it.
    """
    day_start, day_end = day_window_utc(day)
    lookback_start = day_start - timedelta(days=LOOKBACK_DAYS)

    # half-open window: lookback_start <= created_on < day_end
    statement = (
        select(Transaction)
        .where(Transaction.created_on >= lookback_start)
        .where(Transaction.created_on < day_end)
        .order_by(Transaction.created_on)
    )
    transactions = pd.read_sql(statement, db.connection())

    logger.info("transactions_loaded_for_analysis", day=str(day), count=len(transactions))
    return transactions


def list_transactions(
    db: Session,
    day: date,
    page: int,
    page_size: int,
    transaction_type: TransactionType | None,
    state: TransactionState | None,
) -> TransactionPage:
    """
    Returns one page of a day's transactions, newest first, with optional filters.
    """
    day_start, day_end = day_window_utc(day)

    # conditions shared by the count query and the page query
    filters = [
        Transaction.created_on >= day_start,
        Transaction.created_on < day_end,
    ]
    if transaction_type is not None:
        filters.append(Transaction.type == transaction_type)
    if state is not None:
        filters.append(Transaction.state == state)

    # 1. how many rows match in total (for the client to know how many pages exist)
    count_statement = select(func.count()).select_from(Transaction).where(*filters)
    total = db.scalar(count_statement)

    # 2. only the rows for the requested page
    offset = (page - 1) * page_size                     # page 1 -> skip 0, page 2 -> skip page_size, ...
    page_statement = (
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.created_on.desc(), Transaction.idx)
        .offset(offset)
        .limit(page_size)
    )
    transactions = db.scalars(page_statement).all()

    items = []
    for transaction in transactions:
        items.append(TransactionRead.model_validate(transaction))

    logger.info("transactions_listed", day=str(day), page=page, total=total)
    return TransactionPage(items=items, page=page, page_size=page_size, total=total)
