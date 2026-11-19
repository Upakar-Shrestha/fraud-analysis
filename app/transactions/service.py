from sqlalchemy.dialects.postgresql import insert   
from sqlalchemy.orm import Session
import structlog

from app.transactions.helper import generate_transactions
from app.transactions.model import Transaction
from app.transactions.schema import SeedData, SeedRequest

logger = structlog.get_logger(__name__)

def create_transactions(db: Session, request: SeedRequest) -> SeedData:
    """
    Creates and inserts multiple transactions rows in the database.
    """
    rows = generate_transactions(request.seed, request.end_date)

    statement = (
        insert(Transaction)
        .on_conflict_do_nothing(index_elements=[Transaction.id])
        .returning(Transaction.id)
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