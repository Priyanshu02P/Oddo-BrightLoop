"""Bulk billing runs (FR-5.2, FR-5.9, NFR-2, NFR-3, NFR-7).

A run works through due subscriptions in batches until none are left or its
time budget is spent, then stays Running so the next trigger resumes it. Every
subscription is billed in its own transaction under a row lock; one failure is
recorded and the run moves on. Repeating or overlapping invocations are safe:
the invoice uniqueness constraint and the one-result-per-run constraint stop
anything from being billed or recorded twice.
"""

import logging
import time

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission
from apps.subscriptions.models import Subscription

from . import selectors, services
from .exceptions import BillingError, SkipSubscription
from .models import BillingRun, BillingRunResult

logger = logging.getLogger(__name__)

Outcome = BillingRunResult.Outcome
UNEXPECTED_FAILURE = "Unexpected error while generating the invoice. Details are in the server log."


def deadline_from_now():
    return time.monotonic() + settings.BILLING_TIME_BUDGET_SECONDS


def start_or_resume_run(*, trigger, today, actor=None):
    """Return the unfinished run if there is one, otherwise start a new one.

    Resuming instead of starting a second run keeps one result log per run.
    """
    with transaction.atomic():
        running = selectors.running_run()
        if running is not None:
            return running
        run = BillingRun.objects.create(trigger=trigger, triggered_by=actor, run_date=today)
        record_audit(actor=actor, action="billing_run.started", target=run)
    logger.info("Billing run %s started (%s)", run.pk, trigger)
    return run


def start_manual_run(*, actor, today, deadline):
    """The "Run billing now" action for Admin and Staff (FR-5.2)."""
    if not has_permission(actor, Permission.RUN_BILLING):
        raise PermissionDenied
    run = start_or_resume_run(trigger=BillingRun.Trigger.MANUAL, today=today, actor=actor)
    return process_run(run, deadline=deadline)


def continue_run(*, actor, run, deadline):
    if not has_permission(actor, Permission.RUN_BILLING):
        raise PermissionDenied
    return process_run(run, deadline=deadline)


def process_run(run, *, deadline):
    """Bill due subscriptions until done or past `deadline` (time.monotonic())."""
    while run.status == BillingRun.Status.RUNNING and time.monotonic() < deadline:
        batch = list(
            selectors.due_for_run(run).values_list("pk", flat=True)[: settings.BILLING_BATCH_SIZE]
        )
        if not batch:
            _finish(run)
            break
        for subscription_id in batch:
            _process_subscription(run, subscription_id)
            if time.monotonic() >= deadline:
                break
    run.refresh_from_db()
    return run


def _record(run, subscription_id, outcome, *, invoice=None, reason=""):
    return BillingRunResult.objects.create(
        run=run,
        subscription_id=subscription_id,
        outcome=outcome,
        invoice=invoice,
        reason=reason[:300],
    )


def _record_failure(run, subscription_id, reason):
    try:
        with transaction.atomic():
            return _record(run, subscription_id, Outcome.FAILED, reason=reason)
    except IntegrityError:
        return None  # an overlapping invocation already recorded this subscription


def _process_subscription(run, subscription_id):
    """Bill one subscription and record exactly one result for it in this run."""
    try:
        with transaction.atomic():
            subscription = (
                Subscription.objects.select_for_update(of=("self",))
                .select_related("plan", "payment_terms", "customer__user")
                .get(pk=subscription_id)
            )
            if run.results.filter(subscription_id=subscription_id).exists():
                return None  # handled by an overlapping invocation of this run
            try:
                invoice = services.generate_invoice(
                    subscription, today=run.run_date, actor=run.triggered_by
                )
            except SkipSubscription as exc:
                return _record(run, subscription_id, Outcome.SKIPPED, reason=str(exc))
            return _record(run, subscription_id, Outcome.CREATED, invoice=invoice)
    except BillingError as exc:
        logger.warning("Billing run %s: subscription %s failed: %s", run.pk, subscription_id, exc)
        return _record_failure(run, subscription_id, str(exc))
    except Exception:  # per-subscription isolation (FR-5.9): log with context, continue
        logger.exception("Billing run %s: subscription %s failed", run.pk, subscription_id)
        return _record_failure(run, subscription_id, UNEXPECTED_FAILURE)


def _finish(run):
    finished = BillingRun.objects.filter(pk=run.pk, status=BillingRun.Status.RUNNING).update(
        status=BillingRun.Status.COMPLETED, finished_at=timezone.now()
    )
    if finished:
        record_audit(actor=run.triggered_by, action="billing_run.completed", target=run)
        logger.info("Billing run %s completed", run.pk)
    run.refresh_from_db()
