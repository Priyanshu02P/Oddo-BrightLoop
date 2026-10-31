import time
from datetime import date

import pytest
from django.core.exceptions import PermissionDenied

from apps.billing import billing_runs, selectors, services, tasks
from apps.billing.models import BillingRun, BillingRunResult, Invoice
from apps.subscriptions.models import Subscription

from .factories import TODAY, due_subscription

pytestmark = pytest.mark.django_db

Outcome = BillingRunResult.Outcome
FAR_FUTURE = float("inf")


def manual_run(actor, today=TODAY, deadline=FAR_FUTURE):
    return billing_runs.start_manual_run(actor=actor, today=today, deadline=deadline)


def outcomes(run):
    return {r.subscription_id: (r.outcome, r.reason) for r in run.results.all()}


def test_a_run_invoices_every_due_subscription_and_completes(staff_user):
    due = [due_subscription() for _ in range(3)]
    run = manual_run(staff_user)
    assert run.status == BillingRun.Status.COMPLETED
    assert run.finished_at is not None
    assert (run.trigger, run.triggered_by) == (BillingRun.Trigger.MANUAL, staff_user)
    assert {pk: o for pk, (o, _) in outcomes(run).items()} == {s.pk: Outcome.CREATED for s in due}
    assert Invoice.objects.filter(status=Invoice.Status.DRAFT).count() == 3
    counts = selectors.run_with_counts(run.pk)
    assert (counts.processed, counts.created, counts.skipped, counts.failed) == (3, 3, 0, 0)


def test_paused_closed_and_future_subscriptions_are_not_billed(admin_user):
    due_subscription(status=Subscription.Status.PAUSED)
    due_subscription(status=Subscription.Status.CLOSED)
    due_subscription(next_billing_date=date(2026, 7, 2))
    run = manual_run(admin_user)
    assert run.results.count() == 0
    assert not Invoice.objects.exists()


def test_customers_cannot_start_a_run(customer_user):
    with pytest.raises(PermissionDenied):
        manual_run(customer_user)
    assert not BillingRun.objects.exists()


def test_rerunning_does_not_bill_twice(staff_user):
    due_subscription()
    manual_run(staff_user)
    second = manual_run(staff_user)
    assert second.results.count() == 0
    assert Invoice.objects.count() == 1


def test_one_failing_subscription_does_not_stop_the_run(staff_user, monkeypatch, caplog):
    bad, good = due_subscription(), due_subscription()
    real = services.generate_invoice

    def flaky(subscription, **kwargs):
        if subscription.pk == bad.pk:
            raise RuntimeError("database hiccup")
        return real(subscription, **kwargs)

    monkeypatch.setattr(services, "generate_invoice", flaky)
    run = manual_run(staff_user)
    result = outcomes(run)
    assert result[good.pk][0] == Outcome.CREATED
    assert result[bad.pk] == (Outcome.FAILED, billing_runs.UNEXPECTED_FAILURE)
    assert "database hiccup" not in result[bad.pk][1]  # internals stay in the log
    assert "database hiccup" in caplog.text
    bad.refresh_from_db()
    assert bad.next_billing_date == TODAY  # rolled back, retried by the next run
    assert run.status == BillingRun.Status.COMPLETED


def test_domain_failures_are_recorded_with_their_reason(staff_user):
    empty = due_subscription(lines=0)
    run = manual_run(staff_user)
    assert outcomes(run)[empty.pk] == (Outcome.FAILED, "The subscription has no lines to invoice.")


def test_a_run_that_runs_out_of_time_is_resumed_without_duplicates(staff_user, settings):
    settings.BILLING_BATCH_SIZE = 2
    due = [due_subscription() for _ in range(5)]
    run = manual_run(staff_user, deadline=time.monotonic() - 1)  # budget already spent
    assert run.status == BillingRun.Status.RUNNING
    assert run.results.count() == 0
    resumed = billing_runs.start_or_resume_run(trigger=BillingRun.Trigger.SCHEDULED, today=TODAY)
    assert resumed.pk == run.pk  # the open run is continued, not replaced
    run = billing_runs.process_run(resumed, deadline=FAR_FUTURE)
    assert run.status == BillingRun.Status.COMPLETED
    assert run.results.count() == 5
    assert Invoice.objects.count() == len(due)


def test_an_overlapping_invocation_skips_subscriptions_already_recorded(staff_user):
    subscription = due_subscription()
    run = billing_runs.start_or_resume_run(
        trigger=BillingRun.Trigger.MANUAL, today=TODAY, actor=staff_user
    )
    first = billing_runs._process_subscription(run, subscription.pk)
    second = billing_runs._process_subscription(run, subscription.pk)
    assert first.outcome == Outcome.CREATED
    assert second is None
    assert run.results.count() == 1
    assert Invoice.objects.count() == 1


def test_scheduled_billing_runs_as_the_system():
    due_subscription()
    summary = tasks.run_scheduled_billing(TODAY)
    run = BillingRun.objects.get()
    assert (run.trigger, run.triggered_by) == (BillingRun.Trigger.SCHEDULED, None)
    assert summary == {
        "run": run.pk,
        "status": "completed",
        "processed": 1,
        "created": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert tasks.run_scheduled_billing(TODAY)["created"] == 0  # safe to repeat


def test_scheduler_finishes_yesterdays_run_then_starts_todays():
    yesterday = date(2026, 6, 30)
    stale = BillingRun.objects.create(trigger=BillingRun.Trigger.SCHEDULED, run_date=yesterday)
    due_subscription(next_billing_date=yesterday, start_date=yesterday)
    due_subscription()
    summary = tasks.run_scheduled_billing(TODAY)
    stale.refresh_from_db()
    assert stale.status == BillingRun.Status.COMPLETED
    assert stale.results.count() == 1  # only what was due on its own date
    assert summary["run"] != stale.pk and summary["created"] == 1


def test_a_backlog_is_billed_one_period_per_run(staff_user):
    subscription = due_subscription(next_billing_date=date(2026, 5, 1), start_date=date(2026, 5, 1))
    manual_run(staff_user)
    manual_run(staff_user)
    periods = list(
        Invoice.objects.filter(subscription=subscription).values_list("period_start", flat=True)
    )
    assert sorted(periods) == [date(2026, 5, 1), date(2026, 6, 1)]
