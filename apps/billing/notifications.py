"""Email boundary for M5 (NFR-9). Callers handle delivery failure themselves."""

from django.conf import settings
from django.core.mail import EmailMessage


def send_invoice_email(invoice):
    body = (
        f"Invoice {invoice.number} for subscription {invoice.subscription.number}\n\n"
        f"Billing period: {invoice.period_start:%Y-%m-%d} to {invoice.period_end:%Y-%m-%d}\n"
        f"Total (including tax): {invoice.total}\n"
        f"Due date: {invoice.due_date:%Y-%m-%d}\n\n"
        "Sign in to the customer portal to view or print this invoice."
    )
    EmailMessage(
        subject=f"Invoice {invoice.number}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer_email],
    ).send(fail_silently=False)
