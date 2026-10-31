"""Scheduled entry point (FR-5.2, FR-10.1). Safe to call repeatedly (FR-10.2)."""

import time

from django.utils import timezone

from . import billing_runs, selectors
from .models import BillingRun


def run_scheduled_billing(today=None):
    """Resume an unfinished run or start today's, within one time budget.

    When the resumed run belonged to an earlier day and finishes with time to
    spare, today's run is started straight away.
    """
    today = today or timezone.localdate()
    deadline = billing_runs.deadline_from_now()
    run = billing_runs.start_or_resume_run(trigger=BillingRun.Trigger.SCHEDULED, today=today)
    run = billing_runs.process_run(run, deadline=deadline)
    if run.status == BillingRun.Status.COMPLETED and run.run_date < today:
        if time.monotonic() < deadline:
            run = billing_runs.start_or_resume_run(
                trigger=BillingRun.Trigger.SCHEDULED, today=today
            )
            run = billing_runs.process_run(run, deadline=deadline)
    counts = selectors.run_with_counts(run.pk)
    return {
        "run": run.pk,
        "status": run.status,
        "processed": counts.processed,
        "created": counts.created,
        "skipped": counts.skipped,
        "failed": counts.failed,
    }
