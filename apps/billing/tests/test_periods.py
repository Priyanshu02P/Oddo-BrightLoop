from datetime import date

import pytest

from apps.billing.exceptions import BillingError
from apps.billing.periods import billing_period, next_period_start

D = date


@pytest.mark.parametrize(
    "billing, start, expected_end, expected_next",
    [
        ("daily", D(2026, 7, 1), D(2026, 7, 1), D(2026, 7, 2)),
        ("weekly", D(2026, 7, 1), D(2026, 7, 7), D(2026, 7, 8)),
        ("monthly", D(2026, 7, 1), D(2026, 7, 31), D(2026, 8, 1)),
        ("monthly", D(2026, 12, 15), D(2027, 1, 14), D(2027, 1, 15)),
        ("yearly", D(2026, 7, 1), D(2027, 6, 30), D(2027, 7, 1)),
    ],
)
def test_period_spans_one_plan_cycle(billing, start, expected_end, expected_next):
    assert billing_period(start, billing, anchor=start) == (start, expected_end, expected_next)


def test_month_end_start_does_not_drift():
    anchor = D(2026, 1, 31)
    feb = next_period_start(anchor, "monthly", anchor)
    mar = next_period_start(feb, "monthly", anchor)
    apr = next_period_start(mar, "monthly", anchor)
    assert (feb, mar, apr) == (D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30))


def test_leap_day_yearly_falls_back_to_feb_28():
    anchor = D(2028, 2, 29)
    assert next_period_start(anchor, "yearly", anchor) == D(2029, 2, 28)
    assert next_period_start(D(2029, 2, 28), "yearly", anchor) == D(2030, 2, 28)


def test_off_schedule_start_keeps_its_own_day():
    """After a resume the next billing date can sit off the original schedule."""
    assert next_period_start(D(2026, 7, 15), "monthly", anchor=D(2026, 1, 1)) == D(2026, 8, 15)


def test_unknown_billing_period_is_a_billing_error():
    with pytest.raises(BillingError):
        next_period_start(D(2026, 7, 1), "fortnightly", D(2026, 7, 1))
