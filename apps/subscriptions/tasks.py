"""Scheduled entry points (FR-10.1). Each is safe to re-run (FR-10.2): a record
that already moved is skipped, and one failing record never stops the rest."""

import logging

from django.utils import timezone

from . import selectors, services
from .exceptions import InvalidSubscriptionTransition, QuotationNotExpired

logger = logging.getLogger(__name__)

SKIPPABLE = (InvalidSubscriptionTransition, QuotationNotExpired)


def _run(subscriptions, action, label):
    done, skipped, failed = [], [], []
    for subscription in subscriptions:
        try:
            action(subscription)
        except SKIPPABLE:
            skipped.append(subscription.pk)  # already handled by an overlapping run
        except Exception:  # per-record isolation: log with the id, continue
            logger.exception("%s failed for subscription %s", label, subscription.pk)
            failed.append(subscription.pk)
        else:
            done.append(subscription.pk)
    logger.info("%s: %s done, %s skipped, %s failed", label, len(done), len(skipped), len(failed))
    return {"done": done, "skipped": skipped, "failed": failed}


def expire_quotations(today=None):
    """Quotation -> Closed once `valid_until` has passed (FR-4.11)."""
    today = today or timezone.localdate()
    return _run(
        selectors.due_for_expiry(today),
        lambda subscription: services.expire_quotation(subscription, today),
        "Quotation expiry",
    )


def activate_due_subscriptions(today=None):
    """Confirmed -> Active on the start date (FR-4.14)."""
    today = today or timezone.localdate()
    return _run(
        selectors.due_for_activation(today),
        lambda subscription: services.activate_subscription(subscription, today),
        "Subscription activation",
    )


def close_plan_subscriptions(plan):
    """Hook for plans.tasks.run_auto_close (FR-3.6): close the plan's open subscriptions.

    Wire it with PLANS_AUTO_CLOSE_HANDLER=apps.subscriptions.tasks.close_plan_subscriptions.
    A record that fails is logged and the hook raises afterwards, so the plan is
    retried on the next run while the other records are still closed.
    """
    result = _run(selectors.open_for_plan(plan), services.close_for_plan_end, "Plan auto-close")
    if result["failed"]:
        raise RuntimeError(f"Plan {plan.pk}: {len(result['failed'])} subscriptions failed to close")
    return result
