from enum import Enum


class RuleCode(str, Enum):
    # one member per rule; the Phase 5 results table will use this as a column type
    HIGH_VELOCITY = "HIGH_VELOCITY"
    HIGH_VALUE = "HIGH_VALUE"
    REPEATED_AMOUNT = "REPEATED_AMOUNT"
    REPEATED_FAILED_ATTEMPTS = "REPEATED_FAILED_ATTEMPTS"
    RAPID_PASS_THROUGH = "RAPID_PASS_THROUGH"
