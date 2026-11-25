from datetime import datetime, timedelta, timezone
import uuid

import pandas as pd

from app.analysis.helper import (
    RuleHit,
    detect_high_value,
    detect_high_velocity,
    detect_repeated_amount,
    detect_rapid_pass_through,
    detect_repeated_failed_attempts,
)

# one fixed target day (UTC) so every test knows exactly what "today" is
START_DAY = datetime(2026, 11, 22, tzinfo=timezone.utc)
END_DAY = START_DAY + timedelta(days=1)
TEN_AM = START_DAY + timedelta(hours=10)


def make_txn(
    user: str,
    created_on: datetime,
    amount: int = 50_000,
    state: str = "COMPLETED",
    txn_type: str = "TRANSFER",
) -> dict:
    # one fake transaction with only the columns the rules read
    return {
        "idx": uuid.uuid4(),
        "source_user_id": user,
        "created_on": created_on,
        "amount": amount,
        "state": state,
        "type": txn_type,
    }


# high velocity 

def run_velocity(txns: list[dict]) -> list[RuleHit]:
    return detect_high_velocity(pd.DataFrame(txns), START_DAY, END_DAY, min_txn_count=12, window_minutes=5)


def test_velocity_flags_12_txns_in_5_minutes():
    txns = [make_txn("W1", TEN_AM + timedelta(seconds=20 * i)) for i in range(12)]    # 12 txns in 3m40s

    hits = run_velocity(txns)

    assert len(hits) == 1
    assert hits[0].user_id == "W1"
    assert len(hits[0].transaction_ids) == 12
    assert hits[0].evidence["txn_count"] == 12


def test_velocity_ignores_11_txns_in_5_minutes():
    txns = [make_txn("W1", TEN_AM + timedelta(seconds=20 * i)) for i in range(11)]    # one short

    assert run_velocity(txns) == []


def test_velocity_ignores_12_txns_spread_over_the_day():
    txns = [make_txn("W1", TEN_AM + timedelta(minutes=30 * i)) for i in range(12)]    # 30 min apart

    assert run_velocity(txns) == []


# high value 

def history_for(user: str, amount: int, count: int = 5) -> list[dict]:
    # past completed txns, one per day before the target day, all the same amount -> median = amount
    return [make_txn(user, START_DAY - timedelta(days=d), amount) for d in range(1, count + 1)]


def run_high_value(txns: list[dict]) -> list[RuleHit]:
    return detect_high_value(
        pd.DataFrame(txns), START_DAY, END_DAY,
        fixed_threshold=10_000_000, median_multiplier=5, min_history_txns=5, lookback_days=30,
    )


def test_high_value_flags_6x_median():
    txns = history_for("W1", 50_000) + [make_txn("W1", TEN_AM, 300_000)]              # 6x median

    hits = run_high_value(txns)

    assert len(hits) == 1
    assert hits[0].evidence["user_median"] == 50_000


def test_high_value_ignores_2x_median():
    txns = history_for("W1", 50_000) + [make_txn("W1", TEN_AM, 100_000)]              # only 2x

    assert run_high_value(txns) == []


def test_high_value_flags_fixed_threshold_without_history():
    txns = [make_txn("W1", TEN_AM, 10_000_000)]                                         # new user, Rs 100,000

    hits = run_high_value(txns)

    assert len(hits) == 1
    assert hits[0].evidence["user_median"] is None


def test_high_value_skips_median_check_with_too_little_history():
    txns = history_for("W1", 50_000, count=4) + [make_txn("W1", TEN_AM, 300_000)]     # 6x, but only 4 past txns

    assert run_high_value(txns) == []


def test_high_value_ignores_refunds():
    txns = [make_txn("M1", TEN_AM, 10_000_000, txn_type="REFUND")]

    assert run_high_value(txns) == []

# repeated amount
def run_repeated_amount(txns: list[dict]) -> list[RuleHit]:
    return detect_repeated_amount(
        pd.DataFrame(txns), 
        START_DAY, 
        END_DAY,
        min_count=8, 
        time_window_minutes=10, 
        amount_tolerance=0.01,
    )

def test_repeated_amount_flags_8_txns_same_amount_in_10min():
    txns = [make_txn("W1", TEN_AM + timedelta(minutes=i), 999900) for i in range(8)]

    hits = run_repeated_amount(txns)

    assert len(hits) == 1
    assert len(hits[0].transaction_ids) == 8
    assert hits[0].evidence["repeated_amount"] == 999900

def test_repeated_amount_flags_near_identical_txns():
    amounts = [999_900, 995_000, 999_900, 998_000, 999_900, 999_900, 997_500, 999_900]   # all within 1%
    txns = [make_txn("W1", TEN_AM + timedelta(minutes=i), a) for i, a in enumerate(amounts)]

    assert len(run_repeated_amount(txns)) == 1

def test_repeated_amount_ignores_7_same_amounts():
    txns = [make_txn("W1", TEN_AM + timedelta(minutes=i), 999_900) for i in range(7)]    # one short

    assert run_repeated_amount(txns) == []


def test_repeated_amount_ignores_different_amounts():
    txns = [make_txn("W1", TEN_AM + timedelta(minutes=i), 100_000 * (i + 1)) for i in range(8)]   # Rs 1,000, 2,000, ...

    assert run_repeated_amount(txns) == []

# ---------- 5.4 repeated failed attempts ----------

def run_failed_attempts(txns: list[dict]) -> list[RuleHit]:
    return detect_repeated_failed_attempts(pd.DataFrame(txns), START_DAY, END_DAY, min_txn_count=7, window_minutes=3)


def test_failed_attempts_flags_7_failed_in_3_minutes():
    txns = [make_txn("W1", TEN_AM + timedelta(seconds=20 * i), state="FAILED") for i in range(7)]   # 7 in 2 min

    hits = run_failed_attempts(txns)

    assert len(hits) == 1
    assert len(hits[0].transaction_ids) == 7
    assert hits[0].evidence["txn_count"] == 7


def test_failed_attempts_ignores_6_failed():
    txns = [make_txn("W1", TEN_AM + timedelta(seconds=20 * i), state="FAILED") for i in range(6)]   # one short

    assert run_failed_attempts(txns) == []


def test_failed_attempts_ignores_completed_txns():
    states = ["FAILED"] * 6 + ["COMPLETED"]                                                       # 7 attempts, only 6 failed
    txns = [make_txn("W1", TEN_AM + timedelta(seconds=20 * i), state=s) for i, s in enumerate(states)]

    assert run_failed_attempts(txns) == []


# ---------- 5.8 rapid pass-through ----------

def make_transfer(
    sender: str, receiver: str | None, created_on: datetime, amount: int, txn_type: str = "TRANSFER"
) -> dict:
    # like make_txn, but with a receiver
    txn = make_txn(sender, created_on, amount, txn_type=txn_type)
    txn["destination_user_id"] = receiver
    return txn


def funnel_in(receiver: str, sender_count: int, amount: int = 200_000) -> list[dict]:
    # sender_count different users each send `amount` to receiver, 30 s apart
    return [
        make_transfer(f"S{n}", receiver, TEN_AM + timedelta(seconds=30 * n), amount)
        for n in range(sender_count)
    ]


def run_pass_through(txns: list[dict]) -> list[RuleHit]:
    return detect_rapid_pass_through(
        pd.DataFrame(txns), START_DAY, END_DAY, min_senders=15, window_minutes=20, min_pass_through_ratio=0.8,
    )


def test_pass_through_flags_15_senders_then_withdraw_90_percent():
    txns = funnel_in("MULE", 15)                                                       # Rs 2,000 x 15 = Rs 30,000 in
    txns.append(make_transfer("MULE", None, TEN_AM + timedelta(minutes=10), 2_700_000, "WITHDRAW"))   # 90% out

    hits = run_pass_through(txns)

    assert len(hits) == 1
    assert hits[0].user_id == "MULE"
    assert len(hits[0].transaction_ids) == 16                                         # 15 in + 1 out
    assert hits[0].evidence["counterparty_count"] == 15
    assert hits[0].evidence["pass_through_ratio"] == 0.9


def test_pass_through_ignores_14_senders():
    txns = funnel_in("MULE", 14)
    txns.append(make_transfer("MULE", None, TEN_AM + timedelta(minutes=10), 2_520_000, "WITHDRAW"))

    assert run_pass_through(txns) == []


def test_pass_through_ignores_account_that_keeps_the_money():
    txns = funnel_in("MULE", 15)                                                       # money in, nothing out

    assert run_pass_through(txns) == []


def test_pass_through_counts_different_senders_not_txns():
    txns = [make_transfer("S1", "MULE", TEN_AM + timedelta(seconds=30 * n), 200_000) for n in range(15)]   # 1 sender
    txns.append(make_transfer("MULE", None, TEN_AM + timedelta(minutes=10), 2_700_000, "WITHDRAW"))

    assert run_pass_through(txns) == []
