from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.plans.models import Plan

from .factories import PlanFactory

pytestmark = pytest.mark.django_db


def test_plan_persists_every_field_and_price_is_decimal():
    plan = PlanFactory(
        name="Gold",
        price="1234.56",
        billing_period="yearly",
        minimum_quantity=3,
        availability_start_date=date(2026, 2, 1),
        availability_end_date=date(2026, 3, 1),
        renewal_mode="automatic",
        auto_close_at_end_date=True,
    )
    saved = Plan.objects.get(pk=plan.pk)
    assert saved.price == Decimal("1234.56") and isinstance(saved.price, Decimal)
    assert (saved.billing_period, saved.renewal_mode) == ("yearly", "automatic")
    assert saved.minimum_quantity == 3
    assert (saved.availability_start_date, saved.availability_end_date) == (
        date(2026, 2, 1),
        date(2026, 3, 1),
    )


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly", "yearly"])
def test_each_billing_period_is_accepted(period):
    PlanFactory(billing_period=period).full_clean()


@pytest.mark.parametrize("mode", ["automatic", "manual"])
def test_each_renewal_mode_is_accepted(mode):
    PlanFactory(renewal_mode=mode).full_clean()


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"billing_period": "hourly"},
        {"renewal_mode": "sometimes"},
        {"price": "-0.01"},
        {"minimum_quantity": 0},
        {"availability_end_date": date(2025, 12, 31)},
    ],
)
def test_invalid_values_are_rejected_by_validation(overrides):
    plan = PlanFactory.build(**overrides)
    with pytest.raises(ValidationError):
        plan.full_clean()


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"billing_period": "hourly"},
        {"renewal_mode": "sometimes"},
        {"price": Decimal("-1")},
        {"minimum_quantity": 0},
        {"availability_end_date": date(2025, 12, 31)},
    ],
)
def test_database_constraints_reject_invalid_rows(overrides):
    with pytest.raises(IntegrityError), transaction.atomic():
        PlanFactory(**overrides)


def test_lifecycle_options_are_stored_independently():
    flags = ("auto_close_at_end_date", "allow_close_early", "allow_pause", "allow_renew")
    for enabled in flags:
        plan = PlanFactory(**{enabled: True})
        saved = Plan.objects.get(pk=plan.pk)
        assert {flag: getattr(saved, flag) for flag in flags} == {
            flag: flag == enabled for flag in flags
        }


def test_enabled_lifecycle_options_lists_only_enabled_labels():
    plan = PlanFactory(allow_pause=True, allow_renew=True)
    assert plan.enabled_lifecycle_options == ["Pause", "Renew"]
    assert PlanFactory().enabled_lifecycle_options == []


def test_availability_boundaries_are_inclusive():
    plan = PlanFactory(
        availability_start_date=date(2026, 3, 1), availability_end_date=date(2026, 3, 31)
    )
    assert plan.is_available_on(date(2026, 3, 1))
    assert plan.is_available_on(date(2026, 3, 31))
    assert not plan.is_available_on(date(2026, 2, 28))
    assert not plan.is_available_on(date(2026, 4, 1))


def test_availability_status_for_a_given_day():
    plan = PlanFactory(
        availability_start_date=date(2026, 3, 1), availability_end_date=date(2026, 3, 31)
    )
    assert plan.availability_on(date(2026, 2, 1)) == Plan.Availability.UPCOMING
    assert plan.availability_on(date(2026, 3, 15)) == Plan.Availability.AVAILABLE
    assert plan.availability_on(date(2026, 4, 1)) == Plan.Availability.ENDED


def test_duplicate_names_are_allowed():
    PlanFactory(name="Same")
    PlanFactory(name="Same")
    assert Plan.objects.filter(name="Same").count() == 2
