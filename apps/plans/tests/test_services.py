import logging
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.plans import selectors, services
from apps.plans.exceptions import PlanNotAvailable
from apps.plans.models import Plan

from .factories import PlanFactory

pytestmark = pytest.mark.django_db


def fields(**overrides):
    data = {
        "name": "Gold",
        "price": Decimal("99.50"),
        "billing_period": "monthly",
        "minimum_quantity": 2,
        "availability_start_date": date(2026, 1, 1),
        "availability_end_date": date(2026, 6, 30),
        "renewal_mode": "automatic",
        "auto_close_at_end_date": True,
        "allow_close_early": False,
        "allow_pause": True,
        "allow_renew": False,
    }
    data.update(overrides)
    return data


def test_admin_creates_a_plan_and_it_is_logged(admin_user, caplog):
    with caplog.at_level(logging.INFO, logger="apps.plans.services"):
        plan = services.create_plan(actor=admin_user, fields=fields())
    saved = Plan.objects.get(pk=plan.pk)
    assert saved.price == Decimal("99.50")
    assert saved.allow_pause and not saved.allow_renew
    assert f"Plan {plan.pk} created by user {admin_user.pk}" in caplog.text


def test_create_rejects_an_invalid_window_and_saves_nothing(admin_user):
    with pytest.raises(ValidationError):
        services.create_plan(
            actor=admin_user, fields=fields(availability_end_date=date(2025, 1, 1))
        )
    assert not Plan.objects.exists()


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_create_or_update(request, user_fixture):
    actor = request.getfixturevalue(user_fixture)
    plan = PlanFactory(name="Original")
    with pytest.raises(PermissionDenied):
        services.create_plan(actor=actor, fields=fields())
    with pytest.raises(PermissionDenied):
        services.update_plan(actor=actor, plan=plan, fields=fields(name="Changed"))
    plan.refresh_from_db()
    assert plan.name == "Original" and Plan.objects.count() == 1


def test_update_changes_plan_and_is_logged(admin_user, caplog):
    plan = PlanFactory(allow_pause=True)
    with caplog.at_level(logging.INFO, logger="apps.plans.services"):
        services.update_plan(
            actor=admin_user, plan=plan, fields=fields(allow_pause=False, allow_renew=True)
        )
    plan.refresh_from_db()
    assert (plan.name, plan.allow_pause, plan.allow_renew) == ("Gold", False, True)
    assert f"Plan {plan.pk} updated by user {admin_user.pk}" in caplog.text


def test_failed_update_leaves_plan_unchanged(admin_user):
    plan = PlanFactory(name="Original")
    with pytest.raises(ValidationError):
        services.update_plan(actor=admin_user, plan=plan, fields=fields(name=" "))
    plan.refresh_from_db()
    assert plan.name == "Original"


def test_require_plan_available_accepts_dates_inside_the_window():
    plan = PlanFactory(
        availability_start_date=date(2026, 3, 1), availability_end_date=date(2026, 3, 31)
    )
    services.require_plan_available(plan, date(2026, 3, 1))
    services.require_plan_available(plan, date(2026, 3, 31))


@pytest.mark.parametrize("start", [date(2026, 2, 28), date(2026, 4, 1)])
def test_require_plan_available_rejects_dates_outside_the_window(start):
    plan = PlanFactory(
        availability_start_date=date(2026, 3, 1), availability_end_date=date(2026, 3, 31)
    )
    with pytest.raises(PlanNotAvailable):
        services.require_plan_available(plan, start)


def test_selector_offers_only_plans_available_on_the_date():
    inside = PlanFactory(
        availability_start_date=date(2026, 3, 1), availability_end_date=date(2026, 3, 31)
    )
    PlanFactory(availability_start_date=date(2026, 4, 1), availability_end_date=date(2026, 4, 30))
    PlanFactory(availability_start_date=date(2026, 1, 1), availability_end_date=date(2026, 2, 28))
    assert list(selectors.list_plans_available_on(date(2026, 3, 15))) == [inside]


def test_existing_plan_outside_window_can_still_be_read():
    plan = PlanFactory(
        availability_end_date=date(2020, 1, 1), availability_start_date=date(2019, 1, 1)
    )
    assert Plan.objects.get(pk=plan.pk) == plan
    assert list(selectors.list_plans_available_on(date(2026, 1, 1))) == []


def test_pending_auto_close_selector():
    ended = PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 6, 30))
    PlanFactory(auto_close_at_end_date=False, availability_end_date=date(2026, 6, 30))
    PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 7, 1))
    PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 7, 2))
    # The end date itself is still inside the window, so it only passes the next day.
    assert list(selectors.list_plans_pending_auto_close(date(2026, 7, 1))) == [ended]
    assert list(selectors.list_plans_pending_auto_close(date(2026, 6, 30))) == []
