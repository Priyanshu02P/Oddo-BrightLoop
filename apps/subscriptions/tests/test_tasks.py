from datetime import date

import pytest

from apps.plans.tests.factories import PlanFactory
from apps.subscriptions import services, tasks
from apps.subscriptions.exceptions import QuotationNotExpired
from apps.subscriptions.models import Subscription

from .factories import SubscriptionFactory

pytestmark = pytest.mark.django_db

Status = Subscription.Status
TODAY = date(2026, 7, 1)


def test_expiry_closes_only_lapsed_quotations_and_is_repeatable():
    lapsed = SubscriptionFactory(status=Status.QUOTATION, valid_until=date(2026, 6, 30))
    open_quote = SubscriptionFactory(status=Status.QUOTATION, valid_until=TODAY)
    first = tasks.expire_quotations(TODAY)
    second = tasks.expire_quotations(TODAY)
    lapsed.refresh_from_db()
    open_quote.refresh_from_db()
    assert first["done"] == [lapsed.pk]
    assert second == {"done": [], "skipped": [], "failed": []}
    assert (lapsed.status, lapsed.closed_reason) == (Status.CLOSED, "expired")
    assert open_quote.status == Status.QUOTATION


def test_expiry_never_closes_a_quotation_that_is_still_valid():
    quote = SubscriptionFactory(status=Status.QUOTATION, valid_until=TODAY)
    with pytest.raises(QuotationNotExpired):
        services.expire_quotation(quote, TODAY)


def test_activation_starts_due_confirmed_subscriptions():
    due = SubscriptionFactory(status=Status.CONFIRMED, start_date=date(2026, 6, 15))
    later = SubscriptionFactory(status=Status.CONFIRMED, start_date=date(2026, 8, 1))
    result = tasks.activate_due_subscriptions(TODAY)
    due.refresh_from_db()
    later.refresh_from_db()
    assert result["done"] == [due.pk]
    assert (due.status, due.next_billing_date) == (Status.ACTIVE, date(2026, 6, 15))
    assert later.status == Status.CONFIRMED
    assert tasks.activate_due_subscriptions(TODAY)["done"] == []


def test_one_failing_record_does_not_stop_the_rest(monkeypatch):
    bad = SubscriptionFactory(status=Status.CONFIRMED, start_date=date(2026, 6, 1))
    good = SubscriptionFactory(status=Status.CONFIRMED, start_date=date(2026, 6, 1))
    real = services.activate_subscription

    def flaky(subscription, today):
        if subscription.pk == bad.pk:
            raise RuntimeError("boom")
        return real(subscription, today)

    monkeypatch.setattr(services, "activate_subscription", flaky)
    result = tasks.activate_due_subscriptions(TODAY)
    good.refresh_from_db()
    assert (result["done"], result["failed"]) == ([good.pk], [bad.pk])
    assert good.status == Status.ACTIVE


def test_plan_auto_close_hook_closes_open_subscriptions_only():
    plan = PlanFactory()
    active = SubscriptionFactory(plan=plan, status=Status.ACTIVE)
    paused = SubscriptionFactory(plan=plan, status=Status.PAUSED)
    draft = SubscriptionFactory(plan=plan, status=Status.DRAFT)
    other = SubscriptionFactory(status=Status.ACTIVE)
    tasks.close_plan_subscriptions(plan)
    tasks.close_plan_subscriptions(plan)
    for subscription in (active, paused, draft, other):
        subscription.refresh_from_db()
    assert (active.status, active.closed_reason) == (Status.CLOSED, "plan_ended")
    assert paused.status == Status.CLOSED
    assert draft.status == Status.DRAFT
    assert other.status == Status.ACTIVE
