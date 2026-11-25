import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.constants import (
    ACCOUNT_AGE_MAX_DAYS,
    ACTIVE_HOUR_END,
    ACTIVE_HOUR_START,
    AMOUNT_SPREAD,
    ANOMALY_MULTIPLIER,
    BURST_TXN_COUNT,
    BURST_WINDOW_MINUTES,
    CHANNEL_WEIGHTS,
    DAYS,
    FAILED_BURST_COUNT,
    FAILED_BURST_WINDOW_MINUTES,
    FRAUD_CASES_PER_PATTERN,
    FRAUD_WINDOW_DAYS,
    FUNNEL_OUT_RATIO,
    FUNNEL_SENDER_COUNT,
    FUNNEL_WINDOW_MINUTES,
    LOCAL_TIMEZONE,
    MAX_DEVICES_PER_WALLET,
    MAX_TXNS_PER_USER_PER_DAY,
    MERCHANT_WALLET_COUNT,
    REPEATED_AMOUNT,
    REPEATED_TXN_COUNT,
    REPEATED_WINDOW_MINUTES,
    REWARD_AMOUNT_MAX,
    REWARD_AMOUNT_MIN,
    STATUS_WEIGHTS,
    TRANSACTION_TYPE_WEIGHTS,
    TYPICAL_AMOUNT_MAX,
    TYPICAL_AMOUNT_MIN,
    USER_WALLET_COUNT,
    UUID_NAMESPACE,
)
from app.transactions.model import TransactionChannel, TransactionState, TransactionType

LOCAL_TZ = ZoneInfo(LOCAL_TIMEZONE)

# channels a user can start a transfer / load / withdraw from (QR, merchant API, agent are payment/cash only)
SELF_SERVICE_CHANNELS = ("APP", "WEB")


@dataclass
class Population:
    users: list[str]
    merchants: list[str]
    devices: dict[str, list[str]]
    typical_amount: dict[str, int]
    account_created_on: dict[str, datetime]     
    bank_account: dict[str, str]                


def build_population(rng: random.Random, end_date: date) -> Population:
    users = [f"W{n:04d}" for n in range(1, USER_WALLET_COUNT + 1)]
    merchants = [f"M{n:03d}" for n in range(1, MERCHANT_WALLET_COUNT + 1)]
    devices = {
        user: [f"{user}-D{d}" for d in range(1, rng.randint(1, MAX_DEVICES_PER_WALLET) + 1)]
        for user in users
    }
    typical_amount = {user: rng.randint(TYPICAL_AMOUNT_MIN, TYPICAL_AMOUNT_MAX) for user in users}
    # every account exists before the generated history starts
    account_created_on = {
        account: random_utc_time(rng, end_date - timedelta(days=rng.randint(DAYS, ACCOUNT_AGE_MAX_DAYS)))
        for account in users + merchants
    }
    # only the last 4 digits are kept, the rest is masked
    bank_account = {user: f"XXXXXX{rng.randrange(10_000):04d}" for user in users}
    return Population(users, merchants, devices, typical_amount, account_created_on, bank_account)


def build_row(
    population: Population,
    txn_type: TransactionType,
    state: TransactionState,
    source: str | None,
    destination: str | None,
    amount: int,
    device_id: str | None,
    created_on: datetime,
    channel: TransactionChannel,
    external_account: str | None = None,
    parent_txn: uuid.UUID | None = None,
    is_synthetic_fraud: bool = False,
) -> dict:
    return {
        "type": txn_type,
        "state": state,
        "amount": amount,
        "source_user_id": source,
        "source_account_created_on": population.account_created_on[source] if source else None,
        "destination_user_id": destination,
        "external_account": external_account,
        "device_id": device_id,
        "channel": channel,
        "parent_txn": parent_txn,
        "created_on": created_on,
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


def pick_channel(rng: random.Random, txn_type: TransactionType) -> TransactionChannel:
    # channel must make sense for the type
    if txn_type in (TransactionType.CASH_IN, TransactionType.CASH_OUT):
        return TransactionChannel.AGENT_TERMINAL
    if txn_type is TransactionType.REFUND:
        return TransactionChannel.MERCHANT_API
    if txn_type is TransactionType.REWARD:
        return TransactionChannel.APP
    if txn_type is TransactionType.PAYMENT:
        return TransactionChannel(weighted_choice(rng, CHANNEL_WEIGHTS))
    self_service = {channel: CHANNEL_WEIGHTS[channel] for channel in SELF_SERVICE_CHANNELS}
    return TransactionChannel(weighted_choice(rng, self_service))


def other_user(rng: random.Random, population: Population, user: str) -> str:
    # any user except the given one (no self-transfers)
    while True:
        candidate = rng.choice(population.users)
        if candidate != user:
            return candidate


def normal_amount(rng: random.Random, population: Population, user: str) -> int:
    # user's typical amount with some natural variation
    return max(1, int(population.typical_amount[user] * rng.uniform(1 - AMOUNT_SPREAD, 1 + AMOUNT_SPREAD)))


def build_normal_transaction(
    rng: random.Random, population: Population, user: str, day: date, refundable: dict[str, dict]
) -> dict:
    txn_type = TransactionType(weighted_choice(rng, TRANSACTION_TYPE_WEIGHTS))
    # a refund needs an earlier completed payment; without one the user just pays
    if txn_type is TransactionType.REFUND and user not in refundable:
        txn_type = TransactionType.PAYMENT

    state = TransactionState(weighted_choice(rng, STATUS_WEIGHTS))
    channel = pick_channel(rng, txn_type)
    created_on = random_utc_time(rng, day)

    if txn_type is TransactionType.REFUND:
        parent = refundable.pop(user)  # pop: a payment is refunded at most once
        # merchant sends the full amount back; system-initiated, so no device
        return build_row(
            population, txn_type, state, parent["destination_user_id"], user, parent["amount"],
            None, created_on, channel, parent_txn=parent["idx"],
        )
    if txn_type is TransactionType.REWARD:
        # system cashback: no source user, no device
        return build_row(
            population, txn_type, state, None, user, rng.randint(REWARD_AMOUNT_MIN, REWARD_AMOUNT_MAX),
            None, created_on, channel,
        )

    source, destination, external_account = user, None, None
    if txn_type is TransactionType.LOAD:
        source, destination, external_account = None, user, population.bank_account[user]  # bank -> wallet
    elif txn_type is TransactionType.CASH_IN:
        source, destination = None, user                                                    # cash at agent -> wallet
    elif txn_type is TransactionType.WITHDRAW:
        external_account = population.bank_account[user]                                    # wallet -> bank
    elif txn_type is TransactionType.TRANSFER:
        destination = other_user(rng, population, user)
    elif txn_type is TransactionType.PAYMENT:
        destination = rng.choice(population.merchants)
    # CASH_OUT: wallet -> cash at agent, no destination wallet

    return build_row(
        population, txn_type, state, source, destination, normal_amount(rng, population, user),
        rng.choice(population.devices[user]), created_on, channel, external_account,
    )


# planted fraud: each function returns the rows of one case, all marked is_synthetic_fraud

def plant_velocity_burst(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # many transfers packed into a few minutes
    start = random_utc_time(rng, day)
    step_seconds = BURST_WINDOW_MINUTES * 60 // BURST_TXN_COUNT
    return [
        build_row(
            population, TransactionType.TRANSFER, TransactionState.COMPLETED,
            user, other_user(rng, population, user),
            normal_amount(rng, population, user), population.devices[user][0],
            start + timedelta(seconds=i * step_seconds), TransactionChannel.APP, is_synthetic_fraud=True,
        )
        for i in range(BURST_TXN_COUNT)
    ]


def plant_amount_anomaly(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # one payment far above what this user normally spends
    return [
        build_row(
            population, TransactionType.PAYMENT, TransactionState.COMPLETED,
            user, rng.choice(population.merchants),
            population.typical_amount[user] * ANOMALY_MULTIPLIER, population.devices[user][0],
            random_utc_time(rng, day), pick_channel(rng, TransactionType.PAYMENT), is_synthetic_fraud=True,
        )
    ]


def plant_repeated_amount(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # same amount sent again and again in a few minutes (e.g. Rs 9,999 to stay under a limit)
    start = random_utc_time(rng, day)
    step_seconds = REPEATED_WINDOW_MINUTES * 60 // REPEATED_TXN_COUNT
    return [
        build_row(
            population, TransactionType.TRANSFER, TransactionState.COMPLETED,
            user, other_user(rng, population, user), REPEATED_AMOUNT, population.devices[user][0],
            start + timedelta(seconds=i * step_seconds), TransactionChannel.APP, is_synthetic_fraud=True,
        )
        for i in range(REPEATED_TXN_COUNT)
    ]


def plant_failed_burst(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # many failed attempts to the same destination in a couple of minutes
    start = random_utc_time(rng, day)
    destination = other_user(rng, population, user)
    step_seconds = FAILED_BURST_WINDOW_MINUTES * 60 // FAILED_BURST_COUNT
    return [
        build_row(
            population, TransactionType.TRANSFER, TransactionState.FAILED,
            user, destination, normal_amount(rng, population, user), population.devices[user][0],
            start + timedelta(seconds=i * step_seconds), TransactionChannel.APP, is_synthetic_fraud=True,
        )
        for i in range(FAILED_BURST_COUNT)
    ]


def plant_funnel(rng: random.Random, population: Population, user: str, day: date) -> list[dict]:
    # many different users send in, then most of the total leaves to the user's bank (mule)
    start = random_utc_time(rng, day)
    senders = rng.sample([u for u in population.users if u != user], FUNNEL_SENDER_COUNT)
    # +1 slot so the withdrawal is the last txn and still inside the window
    step_seconds = FUNNEL_WINDOW_MINUTES * 60 // (FUNNEL_SENDER_COUNT + 1)
    rows = [
        build_row(
            population, TransactionType.TRANSFER, TransactionState.COMPLETED,
            sender, user, normal_amount(rng, population, sender), population.devices[sender][0],
            start + timedelta(seconds=i * step_seconds), TransactionChannel.APP, is_synthetic_fraud=True,
        )
        for i, sender in enumerate(senders)
    ]
    total_received = sum(row["amount"] for row in rows)
    rows.append(
        build_row(
            population, TransactionType.WITHDRAW, TransactionState.COMPLETED,
            user, None, int(total_received * FUNNEL_OUT_RATIO), population.devices[user][0],
            start + timedelta(seconds=FUNNEL_SENDER_COUNT * step_seconds), TransactionChannel.APP,
            population.bank_account[user], is_synthetic_fraud=True,
        )
    )
    return rows


# order follows the senior's rule numbers: 5.1, 5.2, 5.3, 5.4, 5.8
FRAUD_PLANTERS = [
    plant_velocity_burst,
    plant_amount_anomaly,
    plant_repeated_amount,
    plant_failed_burst,
    plant_funnel,
]


def generate_transactions(seed: int, end_date: date) -> list[dict]:
    rng = random.Random(seed)
    population = build_population(rng, end_date)
    days = [end_date - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    rows = []

    def add(row: dict) -> dict:
        # deterministic ids: re-seeding with the same inputs hits ON CONFLICT DO NOTHING;
        # assigned on add so a later refund can point at its parent's idx
        row["idx"] = uuid.uuid5(UUID_NAMESPACE, f"{seed}:{end_date.isoformat()}:{len(rows)}")
        rows.append(row)
        return row

    refundable: dict[str, dict] = {}  # user -> latest completed payment from an earlier day
    for day in days:
        todays_payments = {}
        for user in population.users:
            for _ in range(rng.randint(0, MAX_TXNS_PER_USER_PER_DAY)):
                row = add(build_normal_transaction(rng, population, user, day, refundable))
                if row["type"] is TransactionType.PAYMENT and row["state"] is TransactionState.COMPLETED:
                    todays_payments[user] = row
        # made refundable only from the next day, so a refund is always after its payment
        refundable.update(todays_payments)

    # fraud only in the last days so every case has enough normal history before it
    fraud_days = days[-FRAUD_WINDOW_DAYS:]
    fraud_users = rng.sample(population.users, len(FRAUD_PLANTERS) * FRAUD_CASES_PER_PATTERN)
    for pattern_idx, plant in enumerate(FRAUD_PLANTERS):
        for case in range(FRAUD_CASES_PER_PATTERN):
            user = fraud_users[pattern_idx * FRAUD_CASES_PER_PATTERN + case]
            for row in plant(rng, population, user, rng.choice(fraud_days)):
                add(row)
    return rows

def day_window_utc(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)   # local midnight
    end = start + timedelta(days=1)                            # next local midnight
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
