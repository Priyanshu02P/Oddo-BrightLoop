"""Overdue reminders (FR-7.8, §8).

Each invoice gets the latest reminder stage it has reached (cadence in
settings.DUNNING_CADENCE_DAYS, working assumption from Open Item C: 1, 7 and
14 days past due). Earlier stages that were never sent are not sent late, so a
long-overdue invoice is not flooded with reminders. A stage is sent once; a
failed send is retried by later runs up to DUNNING_MAX_ATTEMPTS.

The final action after the last reminder (auto-pause the subscription) is not
applied: the specification defers it until Open Item C is confirmed.
"""

import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice

from . import notifications, selectors
from .models import DunningReminder

logger = logging.getLogger(__name__)

SEND_FAILED = "The mail server did not accept the reminder. It will be retried."


def stage_for(days_past_due):
    """Highest reminder stage reached after `days_past_due` days, or None."""
    reached = [i for i, day in enumerate(settings.DUNNING_CADENCE_DAYS, 1) if days_past_due >= day]
    return reached[-1] if reached else None


def send_reminder(invoice_id, stage, today):
    """Send one stage for one invoice. Returns "sent", "failed" or "skipped"."""
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
        days = (today - invoice.due_date).days
        if invoice.status != Invoice.Status.CONFIRMED or stage_for(days) != stage:
            return "skipped"  # paid, cancelled or moved on since it was selected
        reminder, _ = DunningReminder.objects.select_for_update().get_or_create(
            invoice=invoice,
            stage=stage,
            defaults={"days_past_due": days, "status": DunningReminder.Status.FAILED},
        )
        if reminder.status == DunningReminder.Status.SENT:
            return "skipped"  # an overlapping run sent it first
        reminder.attempts += 1
        reminder.last_attempt_at = timezone.now()
        reminder.days_past_due = days
        try:
            notifications.send_overdue_reminder(invoice, stage=stage, days_past_due=days)
        except OSError:
            logger.exception("Reminder %s for invoice %s failed", stage, invoice.pk)
            reminder.status = DunningReminder.Status.FAILED
            reminder.failure_reason = SEND_FAILED
        else:
            reminder.status = DunningReminder.Status.SENT
            reminder.sent_at = reminder.last_attempt_at
            reminder.failure_reason = ""
        reminder.save()
    return reminder.status


def run_dunning(today=None, *, deadline=None):
    """Send every due reminder, stage by stage, within the time budget.

    Safe to repeat: sent stages are never selected again, and the per-row lock
    in send_reminder stops overlapping runs from sending the same stage.
    """
    today = today or timezone.localdate()
    deadline = deadline or time.monotonic() + settings.BILLING_TIME_BUDGET_SECONDS
    counts = {"sent": 0, "failed": 0, "skipped": 0, "complete": True}
    for stage in range(len(settings.DUNNING_CADENCE_DAYS), 0, -1):
        attempted = set()  # a failed send is retried by the next run, not straight away
        while True:
            batch = list(
                selectors.invoices_due_for_reminder(stage, today)
                .exclude(pk__in=attempted)
                .values_list("pk", flat=True)[: settings.DUNNING_BATCH_SIZE]
            )
            if not batch:
                break
            for invoice_id in batch:
                if time.monotonic() >= deadline:
                    counts["complete"] = False
                    logger.info("Dunning run stopped at the time limit: %s", counts)
                    return counts
                attempted.add(invoice_id)
                counts[send_reminder(invoice_id, stage, today)] += 1
    logger.info("Dunning run: %s", counts)
    return counts
