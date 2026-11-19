import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.constants import (
    ACTIVE_HOUR_END,
    ACTIVE_HOUR_START,
    AMOUNT_SPREAD,
    ANOMALY_MULTIPLIER,
    BURST_TXN_COUNT,
    BURST_WINDOW_MINUTES,
    DAYS,
    FAILED_ATTEMPTS_BEFORE_SUCCESS,
    FRAUD_CASES_PER_PATTERN,
    FRAUD_WINDOW_DAYS,
    LOCAL_TIMEZONE,
    MAX_DEVICES_PER_WALLET,
    MAX_TXNS_PER_USER_PER_DAY,
    MERCHANT_WALLET_COUNT,
    NEW_DEVICE_AMOUNT,
    PASS_THROUGH_AMOUNT,
    PASS_THROUGH_OUT_RATIO,
    PASS_THROUGH_WINDOW_MINUTES,
    STATUS_WEIGHTS,
    TRANSACTION_TYPE_WEIGHTS,
    TYPICAL_AMOUNT_MAX,
    TYPICAL_AMOUNT_MIN,
    USER_WALLET_COUNT,
    UUID_NAMESPACE,
)
from app.transactions.model import TransactionStatus, TransactionType

LOCAL_TZ = ZoneInfo(LOCAL_TIMEZONE)


@dataclass
class Population:
    users: list[str]
    merchants: list[str]
    devices: dict[str, list[str]]
    typical_amount: dict[str, int]


def build_population(rng: random.Random) -> Population:
    users = [f"W{n:04d}" for n in range(1, USER_WALLET_COUNT + 1)]
    merchants = [f"M{n:03d}" for n in range(1, MERCHANT_WALLET_COUNT + 1)]
    devices = {
        user: [f"{user}-D{d}" for d in range(1, rng.randint(1, MAX_DEVICES_PER_WALLET) + 1)]
        for user in users
    }
    typical_amount = {user: rng.randint(TYPICAL_AMOUNT_MIN, TYPICAL_AMOUNT_MAX) for user in users}
    return Population(users, merchants, devices, typical_amount)


def build_row(
    transaction_type: TransactionType,
    status: TransactionStatus,
    sender: str | None,
    receiver: str | None,
    amount: int,
    device_id: str,
    transaction_at: datetime,
    is_synthetic_fraud: bool = False,
) -> dict:
    return {
        "transaction_type": transaction_type,
        "status": status,
        "sender_wallet_id": sender,
        "receiver_wallet_id": receiver,
        "amount": amount,
        "device_id": device_id,
        "transaction_at": transaction_at,
        "is_synthetic_fraud": is_synthetic_fraud,
    }


def random_utc_time(rng: random.Random, day: date) -> datetime:
    local = datetime.combine(
        day,
        time(rng.randrange(ACTIVE_HOUR_START, ACTIVE_HOUR_END), rng.randrange(60), rng.randrange(60)),
        tzinfo=LOCAL_TZ,
    )
    return local.astimezone(timezone.utc)


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def other_user(rng: random.Random, population: Population, user: str) -> str:
    # any user except the given one (no self-transfers)
    while True:
        candidate = rng.choice(population.users)
        if candidate != user:
            return candidate


def normal_amount(rng: random.Random, population: Population, user: str) -> int:
    # user's typical amount with some natural variation
    return max(1, int(population.typical_amount[user] * rng.uniform(1 - AMOUNT_SPREAD, 1 + AMOUNT_SPREAD)))


def build_normal_transaction(rng: random.Random, population: Population, user: str, day: date) -> dict:
    transaction_type = TransactionType(weighted_choice(rng, TRANSACTION_TYPE_WEIGHTS))
    sender, receiver = user, None  # BILL_PAYMENT / BANK_WITHDRAWAL: external receiver
    if transaction_type is TransactionType.TOPUP:
        sender, receiver = None, user
    elif transaction_type is TransactionType.P2P_TRANSFER:
        receiver = other_user(rng, population, user)
    elif transaction_type is TransactionType.MERCHANT_PAYMENT:
        receiver = rng.choice(population.merchants)
    return build_row(
        transaction_type,
        TransactionStatus(weighted_choice(rng, STATUS_WEIGHTS)),
        sender,
        receiver,
        normal_amount(rng, population, user),
        rng.choice(population.devices[user]),
        random_utc_time(rng, day),
    )


# planted fraud: each function returns the rows of one case, all marked is_synthetic_fraud

def plant_velocity_burst(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # many transfers packed into a few minutes
    start = random_utc_time(rng, day)
    step_seconds = BURST_WINDOW_MINUTES * 60 // BURST_TXN_COUNT
    return [
        build_row(
            TransactionType.P2P_TRANSFER, TransactionStatus.COMPLETED,
            user, other_user(rng, population, user),
            normal_amount(rng, population, user), population.devices[user][0],
            start + timedelta(seconds=i * step_seconds), True,
        )
        for i in range(BURST_TXN_COUNT)
    ]


def plant_amount_anomaly(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # one payment far above what this user normally spends
    return [
        build_row(
            TransactionType.MERCHANT_PAYMENT, TransactionStatus.COMPLETED,
            user, rng.choice(population.merchants),
            population.typical_amount[user] * ANOMALY_MULTIPLIER, population.devices[user][0],
            random_utc_time(rng, day), True,
        )
    ]


def plant_failed_then_success(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # several failed attempts, one minute apart, then a success
    start = random_utc_time(rng, day)
    receiver = other_user(rng, population, user)
    amount = normal_amount(rng, population, user)
    statuses = [TransactionStatus.FAILED] * FAILED_ATTEMPTS_BEFORE_SUCCESS + [TransactionStatus.COMPLETED]
    return [
        build_row(
            TransactionType.P2P_TRANSFER, status, user, receiver, amount,
            population.devices[user][0], start + timedelta(minutes=i), True,
        )
        for i, status in enumerate(statuses)
    ]


def plant_new_device_high_value(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # high-value withdrawal from a device id never seen in this user's history
    return [
        build_row(
            TransactionType.BANK_WITHDRAWAL, TransactionStatus.COMPLETED,
            user, None, NEW_DEVICE_AMOUNT, f"{user}-NEW",
            random_utc_time(rng, day), True,
        )
    ]


def plant_pass_through(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    received_at = random_utc_time(rng, day)
    sender = other_user(rng, population, user)
    sent_at = received_at + timedelta(minutes=rng.randint(5, PASS_THROUGH_WINDOW_MINUTES))
    return [
        build_row(
            TransactionType.P2P_TRANSFER, TransactionStatus.COMPLETED,
            sender, user, PASS_THROUGH_AMOUNT, population.devices[sender][0], received_at, True,
        ),
        build_row(
            TransactionType.BANK_WITHDRAWAL, TransactionStatus.COMPLETED,
            user, None, int(PASS_THROUGH_AMOUNT * PASS_THROUGH_OUT_RATIO),
            population.devices[user][0], sent_at, True,
        ),
    ]


FRAUD_PLANTERS = [
    plant_velocity_burst,
    plant_amount_anomaly,
    plant_failed_then_success,
    plant_new_device_high_value,
    plant_pass_through,
]


def generate_transactions(seed: int, end_date: date) -> list[dict]:
    rng = random.Random(seed)
    population = build_population(rng)
    days = [end_date - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]

    rows = []
    for day in days:
        for user in population.users:
            for _ in range(rng.randint(0, MAX_TXNS_PER_USER_PER_DAY)):
                rows.append(build_normal_transaction(rng, population, user, day))

    # fraud only in the last days so every case has enough normal history before it
    fraud_days = days[-FRAUD_WINDOW_DAYS:]
    fraud_users = rng.sample(population.users, len(FRAUD_PLANTERS) * FRAUD_CASES_PER_PATTERN)
    for pattern_idx, plant in enumerate(FRAUD_PLANTERS):
        for case in range(FRAUD_CASES_PER_PATTERN):
            user = fraud_users[pattern_idx * FRAUD_CASES_PER_PATTERN + case]
            rows.extend(plant(rng, population, user, rng.choice(fraud_days)))

    # deterministic ids: re-seeding with the same inputs hits ON CONFLICT DO NOTHING
    for index, row in enumerate(rows):
        row["id"] = uuid.uuid5(UUID_NAMESPACE, f"{seed}:{end_date.isoformat()}:{index}")
    return rows
