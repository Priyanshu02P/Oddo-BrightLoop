"""Email boundary for M4 (NFR-9). Callers handle delivery failure themselves."""

from django.conf import settings
from django.core.mail import EmailMessage


def send_quotation_email(subscription):
    body = (
        f"Your quotation {subscription.number} is ready to review.\n\n"
        f"Total (including tax): {subscription.total}\n"
        f"Valid until: {subscription.valid_until:%Y-%m-%d}\n\n"
        "Sign in to the customer portal to review and accept it."
    )
    EmailMessage(
        subject=f"Quotation {subscription.number}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscription.customer.user.email],
    ).send(fail_silently=False)
