import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from app.analysis.model import RuleCode
from app.transactions.model import TransactionState, TransactionType


@dataclass
class RuleHit:
    rule: RuleCode
    user_id: str
    transaction_ids: list[uuid.UUID]
    evidence: dict  


def detect_high_velocity(
    transactions: pd.DataFrame,
    start_day: datetime,
    end_day: datetime,
    min_txn_count: int,
    window_minutes: int,
) -> list[RuleHit]:
    """
    flags users who started min_txn_count or more txns within window_minutes on the target day.
    """
    window = timedelta(minutes=window_minutes)

    todays = transactions[
        transactions["source_user_id"].notna()
        & (transactions["created_on"] >= start_day)
        & (transactions["created_on"] < end_day)
    ]

    hits = []
    for user_id, user_txns in todays.groupby("source_user_id"):
        user_txns = user_txns.sort_values("created_on")
        times = user_txns["created_on"].tolist()
        ids = user_txns["idx"].tolist()

        flagged_ids = set()
        biggest_count = 0

        # start a window at each txn and count the user's txns inside it
        for i in range(len(times)):
            window_end = times[i] + window
            in_window = [ids[j] for j in range(i, len(times)) if times[j] <= window_end]

            if len(in_window) >= min_txn_count:
                flagged_ids.update(in_window)
                biggest_count = max(biggest_count, len(in_window))

        if flagged_ids:
            hits.append(
                RuleHit(
                    rule=RuleCode.HIGH_VELOCITY,
                    user_id=user_id,
                    transaction_ids=list(flagged_ids),
                    evidence={
                        "txn_count": biggest_count,         # most txns found in one window
                        "window_minutes": window_minutes,
                    },
                )
            )
    return hits

def detect_high_value(
    transactions: pd.DataFrame,
    start_day: datetime,
    end_day: datetime,
    fixed_threshold: int,
    median_multiplier: float,
    min_history_txns: int,
    lookback_days: int,
) -> list[RuleHit]:
    """
    flags target-day txns at or above fixed_threshold, or at least median_multiplier x the user's past median.
    """
    # only txns a user sent (LOAD, CASH_IN, REWARD have no sender)
    sent = transactions[
        transactions["source_user_id"].notna()
        & (transactions["type"] != TransactionType.REFUND.value)    # refunds return money, not spending
    ]

    # the user's normal spending = completed txns they sent in the lookback days before the target day
    history = sent[
        (sent["created_on"] >= start_day - timedelta(days=lookback_days))
        & (sent["created_on"] < start_day)
        & (sent["state"] == TransactionState.COMPLETED.value)     # .value: pandas compares the plain text "COMPLETED"
    ]

    # one number per user, as plain dicts like {"W0001": 52000.0, "W0002": 310000.0}
    user_median = history.groupby("source_user_id")["amount"].median().to_dict()
    user_history_count = history.groupby("source_user_id")["amount"].count().to_dict()

    # the target day's txns we are judging
    todays = sent[(sent["created_on"] >= start_day) & (sent["created_on"] < end_day)]

    hits = []
    for txn in todays.itertuples():
        user_id = txn.source_user_id
        amount = int(txn.amount)
        median = user_median.get(user_id)                   # None if the user has no history
        past_count = user_history_count.get(user_id, 0)

        # check if the transaction is big no matter who sends it
        over_threshold = amount >= fixed_threshold

        # check if the transaction is big for this user (only when there is enough history to trust the median)
        over_median = past_count >= min_history_txns and amount >= median * median_multiplier

        if not over_threshold and not over_median:
            continue                                        # normal txn, move to the next one

        hits.append(
            RuleHit(
                rule=RuleCode.HIGH_VALUE,
                user_id=user_id,
                transaction_ids=[txn.idx],
                evidence={
                    "amount": amount,
                    "fixed_threshold": fixed_threshold,
                    "user_median": median,
                    "median_multiplier": median_multiplier,
                    "history_txn_count": past_count,
                },
            )
        )
    return hits

def detect_repeated_amount(
        transactions: pd.DataFrame,
        start_day: datetime,
        end_day: datetime,
        min_count: int,
        time_window_minutes: int,
        amount_tolerance: float,
    ) -> list[RuleHit]:
    '''
    flags users who sent the same amount in multiple txns within certain time frame.
    '''
    window = timedelta(minutes=time_window_minutes)

    todays = transactions[
        transactions["source_user_id"].notna()
        & (transactions["created_on"] >= start_day)
        & (transactions["created_on"] < end_day)
    ]

    hits = []
    for user_id, user_txns in todays.groupby("source_user_id"):
        user_txns = user_txns.sort_values("created_on")
        times = user_txns["created_on"].tolist()
        ids = user_txns["idx"].tolist()
        amounts = user_txns["amount"].tolist()

        flagged_ids = set()
        biggest_count = 0

        for i in range(len(times)):
            window_end = times[i] + window
            difference = amounts[i] * amount_tolerance
            similar =[
                ids[j] for j in range(i, len(times))
                if times[j] <= window_end and abs(amounts[j] - amounts[i]) <= difference
            ]

            if len(similar) >= min_count:
                flagged_ids.update(similar)
                if len(similar) > biggest_count:
                    biggest_count = len(similar)
                    repeated_amount = amounts[i]

        if flagged_ids:
            hits.append(
                RuleHit(
                    rule=RuleCode.REPEATED_AMOUNT,
                    user_id=user_id,
                    transaction_ids=list(flagged_ids),
                    evidence={
                        "txn_count": biggest_count,
                        "window_minutes": time_window_minutes,
                        "amount_tolerance": amount_tolerance,
                        "repeated_amount": int(repeated_amount),
                    },
                )
            )
    return hits

def detect_repeated_failed_attempts(
    transactions: pd.DataFrame,
    start_day: datetime,
    end_day: datetime,
    min_txn_count: int,
    window_minutes: int,
) -> list[RuleHit]:
    '''
    flags users who have >= 7 failed attempts within a 3 mins.
    '''
    window = timedelta(minutes=window_minutes)

    todays = transactions[
        transactions["source_user_id"].notna()
        & (transactions["state"] == TransactionState.FAILED.value)
        & (transactions["created_on"] >= start_day)
        & (transactions["created_on"] < end_day)
    ]

    hits = []
    for user_id, user_txns in todays.groupby("source_user_id"):
        user_txns = user_txns.sort_values("created_on")
        times = user_txns["created_on"].tolist()
        ids = user_txns["idx"].tolist()

        flagged_ids = set()
        biggest_count = 0

        for i in range(len(times)):
            window_end = times[i] + window
            in_window = [ids[j] for j in range(i, len(times)) if times[j] <= window_end]

            if len(in_window) >= min_txn_count:
                flagged_ids.update(in_window)
                biggest_count = max(biggest_count, len(in_window))

        if flagged_ids:
            hits.append(
                RuleHit(
                    rule=RuleCode.REPEATED_FAILED_ATTEMPTS,
                    user_id=user_id,
                    transaction_ids=list(flagged_ids),
                    evidence={
                        "txn_count": biggest_count,
                        "window_minutes": window_minutes,
                    },
                )
            )
    return hits

 
def detect_rapid_pass_through(
    transactions: pd.DataFrame,
    start_day: datetime,
    end_day: datetime,
    min_senders: int,
    window_minutes: int,
    min_pass_through_ratio: float,
) -> list[RuleHit]:
    """
    flags accounts that receive money from min_senders or more different users and pass
    at least min_pass_through_ratio of it onward within window_minutes.
    """
    window = timedelta(minutes=window_minutes)

    # only completed txns on the target day actually moved money
    todays = transactions[
        (transactions["state"] == TransactionState.COMPLETED.value)
        & (transactions["created_on"] >= start_day)
        & (transactions["created_on"] < end_day)
    ]

    incoming = todays[todays["source_user_id"].notna() & todays["destination_user_id"].notna()]   # user -> user
    outgoing = todays[todays["source_user_id"].notna()]                                           # anything a user sent

    hits = []
    for user_id, user_in in incoming.groupby("destination_user_id"):
        if user_in["source_user_id"].nunique() < min_senders:
            continue                                    # not enough different senders all day -> skip early

        user_in = user_in.sort_values("created_on")
        user_out = outgoing[outgoing["source_user_id"] == user_id]

        # start a window at each incoming txn
        for window_start in user_in["created_on"].tolist():
            window_end = window_start + window

            in_window = user_in[(user_in["created_on"] >= window_start) & (user_in["created_on"] <= window_end)]
            sender_count = in_window["source_user_id"].nunique()
            if sender_count < min_senders:
                continue                                # too few different senders in this window

            out_window = user_out[(user_out["created_on"] >= window_start) & (user_out["created_on"] <= window_end)]
            total_in = int(in_window["amount"].sum())
            total_out = int(out_window["amount"].sum())
            ratio = total_out / total_in
            if ratio < min_pass_through_ratio:
                continue                                # account kept most of the money

            # funnel found -> flag both the money in and the money out
            last_txn_at = max(in_window["created_on"].max(), out_window["created_on"].max())
            hits.append(
                RuleHit(
                    rule=RuleCode.RAPID_PASS_THROUGH,
                    user_id=user_id,
                    transaction_ids=in_window["idx"].tolist() + out_window["idx"].tolist(),
                    evidence={
                        "counterparty_count": sender_count,
                        "incoming_count": len(in_window),
                        "outgoing_count": len(out_window),
                        "total_in": total_in,
                        "total_out": total_out,
                        "pass_through_ratio": round(ratio, 2),
                        "minutes_taken": round((last_txn_at - window_start).total_seconds() / 60, 1),
                    },
                )
            )
            break                                       # one hit per account per day
    return hits
