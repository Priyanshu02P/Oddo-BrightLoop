from django.db.models import Count, F, Q

from apps.accounts.models import AuditLog
from apps.accounts.permissions import scope_to_customer
from apps.subscriptions.models import Subscription

from .models import BillingRun, BillingRunResult, Invoice

Outcome = BillingRunResult.Outcome

# Drafts are not issued yet, so the portal only shows the rest (M5 assumption).
CUSTOMER_VISIBLE_STATUSES = (
    Invoice.Status.CONFIRMED,
    Invoice.Status.PAID,
    Invoice.Status.CANCELLED,
)


def list_invoices(*, status=None, overdue_on=None, q="", date_from=None, date_to=None):
    """Internal list (UI/UX 5.9): one query per page, filters on indexed columns."""
    invoices = Invoice.objects.select_related("subscription")
    if status:
        invoices = invoices.filter(status=status)
    if overdue_on:
        invoices = invoices.filter(due_date__lt=overdue_on).exclude(status=Invoice.Status.PAID)
    if q:
        invoices = invoices.filter(
            Q(number__icontains=q)
            | Q(customer_email__icontains=q)
            | Q(subscription__number__icontains=q)
        )
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)
    return invoices.order_by("-invoice_date", "-id")


def invoice_detail_queryset():
    return Invoice.objects.select_related("subscription", "customer__user").prefetch_related(
        "lines"
    )


def customer_invoices(user):
    """Every customer-facing read goes through here: scoped to the signed-in
    customer, so another customer's invoice is simply not found (FR-1.7)."""
    visible = invoice_detail_queryset().filter(status__in=CUSTOMER_VISIBLE_STATUSES)
    return scope_to_customer(visible, user).order_by("-invoice_date", "-id")


def list_activity(invoice):
    return (
        AuditLog.objects.select_related("actor")
        .filter(target_type=invoice._meta.label_lower, target_id=invoice.pk)
        .order_by("created_at", "id")
    )


def _with_counts(runs):
    return runs.annotate(
        processed=Count("results"),
        created=Count("results", filter=Q(results__outcome=Outcome.CREATED)),
        skipped=Count("results", filter=Q(results__outcome=Outcome.SKIPPED)),
        failed=Count("results", filter=Q(results__outcome=Outcome.FAILED)),
    )


def list_runs():
    return _with_counts(BillingRun.objects.select_related("triggered_by")).order_by(
        "-started_at", "-id"
    )


def run_with_counts(pk):
    return _with_counts(BillingRun.objects.select_related("triggered_by")).get(pk=pk)


def run_results(run, outcome=None):
    results = run.results.select_related("subscription__customer__user", "invoice")
    if outcome:
        results = results.filter(outcome=outcome)
    return results.order_by("id")


def running_run():
    return (
        BillingRun.objects.filter(status=BillingRun.Status.RUNNING).order_by("started_at").first()
    )


def due_for_run(run):
    """Active subscriptions due on the run date that this run has not handled yet.

    Paused and closed subscriptions are never selected (BR-6). Each run bills
    at most one period per subscription; a backlog is caught up by later runs.
    """
    return (
        Subscription.objects.filter(
            Q(next_billing_date__lte=run.run_date),
            Q(next_billing_date__lte=F("expiry_date")),
            status=Subscription.Status.ACTIVE,
        )
        .exclude(billing_results__run=run)
        .order_by("next_billing_date", "id")
    )
