from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max, Q, Sum

from apps.billing.models import Invoice

from .models import DunningReminder, Payment


def list_payments(*, q="", method=None, status=None, date_from=None, date_to=None):
    """Internal list (UI/UX 5.11): one query per page."""
    payments = Payment.objects.select_related("invoice", "recorded_by")
    if q:
        payments = payments.filter(
            Q(reference__icontains=q)
            | Q(invoice__number__icontains=q)
            | Q(invoice__customer_email__icontains=q)
        )
    if method:
        payments = payments.filter(method=method)
    if status:
        payments = payments.filter(status=status)
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    return payments.order_by("-payment_date", "-id")


def payment_detail_queryset():
    return Payment.objects.select_related("invoice__subscription", "recorded_by")


def payable_invoices():
    """Confirmed invoices with no pending or successful payment (§5.1)."""
    return (
        Invoice.objects.filter(status=Invoice.Status.CONFIRMED)
        .exclude(payments__status__in=[Payment.Status.PENDING, Payment.Status.SUCCEEDED])
        .order_by("due_date", "id")
    )


def overdue_invoices(today):
    """Follow-up list (FR-7.6, §7.5): payable invoices past their due date.

    The overdue rule is today > due_date and not Paid. Drafts and Cancelled
    invoices can't be paid, so they are left out of follow-up (M7 decision 10).
    """
    return (
        Invoice.objects.filter(status=Invoice.Status.CONFIRMED, due_date__lt=today)
        .select_related("subscription")
        .annotate(
            last_reminder=Max(
                "dunning_reminders__stage",
                filter=Q(dunning_reminders__status=DunningReminder.Status.SENT),
            )
        )
        .order_by("due_date", "id")
    )


def receivables_summary(today):
    """Paid vs outstanding at a glance (FR-7.5)."""

    def totals(invoices):
        return invoices.aggregate(count=Count("id"), total=Sum("total"))

    outstanding = Invoice.objects.filter(status=Invoice.Status.CONFIRMED)
    return {
        "outstanding": totals(outstanding),
        "overdue": totals(outstanding.filter(due_date__lt=today)),
        "paid_this_month": totals(
            Invoice.objects.filter(
                status=Invoice.Status.PAID, paid_at__date__gte=today.replace(day=1)
            )
        ),
    }


def invoices_due_for_reminder(stage, today):
    """Confirmed invoices whose latest reached stage is `stage` and that still need it."""
    cadence = settings.DUNNING_CADENCE_DAYS
    invoices = Invoice.objects.filter(
        status=Invoice.Status.CONFIRMED,
        due_date__lte=today - timedelta(days=cadence[stage - 1]),
    )
    if stage < len(cadence):
        invoices = invoices.filter(due_date__gt=today - timedelta(days=cadence[stage]))
    done = DunningReminder.objects.filter(stage__gte=stage, status=DunningReminder.Status.SENT)
    exhausted = DunningReminder.objects.filter(
        stage=stage, attempts__gte=settings.DUNNING_MAX_ATTEMPTS
    )
    return (
        invoices.exclude(pk__in=done.values("invoice_id"))
        .exclude(pk__in=exhausted.values("invoice_id"))
        .order_by("due_date", "id")
    )
