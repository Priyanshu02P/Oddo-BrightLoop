import logging

from django.utils import timezone

from . import selectors

logger = logging.getLogger(__name__)


def run_auto_close(close_subscriptions, today=None):
    """Close subscriptions of every plan whose auto-close end date has passed (FR-3.6).

    `close_subscriptions(plan)` is the M4 hook. It must move each of the plan's
    eligible subscriptions to Closed through the shared transition service,
    skipping ones already closed. It must be safe to repeat, because this job
    re-selects every expired auto-close plan on each run (FR-10.2). The plan
    app never assigns a subscription status itself.

    A plan whose hook raises is logged and skipped; the remaining plans are
    still processed and the failed plan is retried on the next run.
    """
    today = today or timezone.localdate()
    processed, failed = [], []
    for plan in selectors.list_plans_pending_auto_close(today):
        try:
            close_subscriptions(plan)
        except Exception:  # per-plan isolation: log with context, continue, retry next run
            logger.exception("Auto-close failed for plan %s", plan.pk)
            failed.append(plan.pk)
        else:
            processed.append(plan.pk)
    logger.info("Plan auto-close finished: %s processed, %s failed", len(processed), len(failed))
    return {"processed_plan_ids": processed, "failed_plan_ids": failed}
