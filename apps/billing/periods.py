"""Billing-period arithmetic (M5 open decision 3: period representation).

A period starts on the subscription's next billing date and lasts one plan
cycle; it ends the day before the next period starts. Monthly and yearly
periods stay on the subscription's start day, clamped to short months, so a
subscription starting on Jan 31 bills Feb 28, then Mar 31 (no drift). A period
that starts off that schedule (after a resume) keeps its own day of the month.
"""

from calendar import monthrange
from datetime import timedelta

from apps.plans.models import Plan

from .exceptions import BillingError

Period = Plan.BillingPeriod


def _clamped(year, month, day):
    return min(day, monthrange(year, month)[1])


def _add_months(day, months, anchor_day):
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return day.replace(year=year, month=month, day=_clamped(year, month, anchor_day))


def next_period_start(period_start, billing_period, anchor):
    """First day of the period after the one starting on `period_start`.

    `anchor` is the subscription's start date.
    """
    if billing_period == Period.DAILY:
        return period_start + timedelta(days=1)
    if billing_period == Period.WEEKLY:
        return period_start + timedelta(days=7)
    if billing_period in (Period.MONTHLY, Period.YEARLY):
        on_schedule = period_start.day == _clamped(
            period_start.year, period_start.month, anchor.day
        )
        anchor_day = anchor.day if on_schedule else period_start.day
        months = 1 if billing_period == Period.MONTHLY else 12
        return _add_months(period_start, months, anchor_day)
    raise BillingError(f"The plan's billing period “{billing_period}” is not supported.")


def billing_period(period_start, billing_period, anchor):
    """(start, end, next_start) of the period starting on `period_start`."""
    next_start = next_period_start(period_start, billing_period, anchor)
    return period_start, next_start - timedelta(days=1), next_start
