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
# planted cases sit inside the senior's example rules so the detectors can find them
BURST_TXN_COUNT = 12                # 5.1: 12 txns ...
BURST_WINDOW_MINUTES = 4            # ... within 4 min (rule: 12+ in 5 min)
ANOMALY_MULTIPLIER = 10             # 5.2: x user's typical amount
REPEATED_AMOUNT = 999_900           # 5.3: paisa = Rs 9,999
REPEATED_TXN_COUNT = 8              # 5.3: 8 txns ...
REPEATED_WINDOW_MINUTES = 8         # ... within 8 min (rule: 8+ in 10 min)
FAILED_BURST_COUNT = 7              # 5.4: 7 failed txns ...
FAILED_BURST_WINDOW_MINUTES = 2     # ... within 2 min (rule: 7+ in 3 min)
FUNNEL_SENDER_COUNT = 15            # 5.8: 15 distinct users send in ...
FUNNEL_WINDOW_MINUTES = 15          # ... and money leaves within 15 min (rule: 20 min)
FUNNEL_OUT_RATIO = 0.9              # 5.8: share of received money passed onward

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
VELOCITY_MIN_TXN_COUNT = 12         # 5.1: 12+ txns ...
VELOCITY_WINDOW_MINUTES = 5         # ... within 5 min
HIGH_VALUE_THRESHOLD = 10_000_000       # 5.2: paisa = Rs 100,000 (senior's example)
HIGH_VALUE_MEDIAN_MULTIPLIER = 5        # 5.2: 5x the user's median or more
HIGH_VALUE_MIN_HISTORY_TXNS = 5         # 5.2: fewer past txns -> median not trusted, only fixed threshold
REPEATED_AMOUNT_MIN_COUNT = 8           # 5.3: 8+ txns ...
REPEATED_AMOUNT_WINDOW_MINUTES = 10     # ... within 10 min
REPEATED_AMOUNT_TOLERANCE = 0.01       # ... amounts within 1% of each other
FAILED_MIN_TXN_COUNT = 7                # 5.4: 7+ failed txns ...
FAILED_WINDOW_MINUTES = 3               # ... within 3 min
PASS_THROUGH_MIN_SENDERS = 15           # 5.8: money in from 15+ different users ...
PASS_THROUGH_WINDOW_MINUTES = 20        # ... and passed on within 20 min
PASS_THROUGH_MIN_RATIO = 0.8            # ... at least 80% of what came in


'''API constants'''
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200                 # stops one request from pulling the whole table
