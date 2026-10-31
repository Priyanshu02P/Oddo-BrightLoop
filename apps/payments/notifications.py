"""Email boundary for M7 dunning (NFR-9). Callers handle delivery failure themselves."""

from django.conf import settings
from django.core.mail import EmailMessage


def send_overdue_reminder(invoice, *, stage, days_past_due):
    body = (
        f"Invoice {invoice.number} is {days_past_due} day{'s' if days_past_due != 1 else ''} "
        "past its due date.\n\n"
        f"Amount due (including tax): {invoice.total}\n"
        f"Due date: {invoice.due_date:%Y-%m-%d}\n\n"
        "Sign in to the customer portal to view or print the invoice. If you have already "
        "paid, please ignore this reminder."
    )
    EmailMessage(
        subject=f"Payment reminder {stage}: invoice {invoice.number} is overdue",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer_email],
    ).send(fail_silently=False)
