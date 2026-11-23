import uuid

APP_TITLE = "Fraud Analysis API"

'''DB constants'''
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10
DB_POOL_TIMEOUT_SECONDS = 30


'''synthetic data constants'''
DAYS = 45                           
USER_WALLET_COUNT = 200
MERCHANT_WALLET_COUNT = 20
MAX_DEVICES_PER_WALLET = 2
MAX_TXNS_PER_USER_PER_DAY = 5           
ACTIVE_HOUR_START = 7                # 7 am to 10 pm
ACTIVE_HOUR_END = 22
TYPICAL_AMOUNT_MIN = 10_000          # 10000 paisa = Rs 100
TYPICAL_AMOUNT_MAX = 500_000         # 500000 paisa = Rs 5,000
UUID_NAMESPACE = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-1b2d3c4e5f60")  # fixed so IDs are reproducible


FRAUD_WINDOW_DAYS = 7               # fraud planted only in the last 7 days
FRAUD_CASES_PER_PATTERN = 5
BURST_TXN_COUNT = 12                # txns in one burst
BURST_WINDOW_MINUTES = 10           # txns in one burst occur within 10 minutes
ANOMALY_MULTIPLIER = 10             # x user's typical amount
FAILED_ATTEMPTS_BEFORE_SUCCESS = 3
NEW_DEVICE_AMOUNT = 2_500_000       # paisa = Rs 25,000
PASS_THROUGH_AMOUNT = 5_000_000     # paisa = Rs 50,000
PASS_THROUGH_OUT_RATIO = 0.9        # share forwarded out
PASS_THROUGH_WINDOW_MINUTES = 60

LOCAL_TIMEZONE = "Asia/Kathmandu"    
AMOUNT_SPREAD = 0.5                  
TRANSACTION_TYPE_WEIGHTS = {
    "PAYMENT": 0.40,        # merchant + bill payments (was MERCHANT_PAYMENT 0.30 + BILL_PAYMENT 0.15)
    "TRANSFER": 0.33,       # was P2P_TRANSFER
    "LOAD": 0.10,           # was TOPUP
    "WITHDRAW": 0.05,
    "CASH_IN": 0.04,
    "CASH_OUT": 0.04,
    "REFUND": 0.02,         # links to an earlier PAYMENT via parent_txn
    "REWARD": 0.02,
}
STATUS_WEIGHTS = {
    "COMPLETED": 0.92,
    "FAILED": 0.03,
    "PENDING": 0.01,
    "ON_HOLD": 0.01,
    "INITIATED": 0.01,
    "REFUNDED": 0.01,
    "CANCELED": 0.01,
}
CHANNEL_WEIGHTS = {
    "APP": 0.60,
    "QR": 0.20,
    "WEB": 0.08,
    "MERCHANT_API": 0.07,
    "AGENT_TERMINAL": 0.05,
}
ACCOUNT_AGE_MAX_DAYS = 730          # accounts are 45 days to 2 years old
REWARD_AMOUNT_MIN = 1_000           # paisa = Rs 10 cashback
REWARD_AMOUNT_MAX = 10_000          # paisa = Rs 100 cashback


'''analysis constants'''
LOOKBACK_DAYS = 30                  # history loaded before the target day (for the 30-day median rule)


'''API constants'''
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200                 # stops one request from pulling the whole table
