"""Invoice writes: generation, lifecycle, delivery (FR-5.1, FR-5.3 to FR-5.7, FR-5.10)."""

import logging
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission
from apps.subscriptions.models import Subscription
from apps.subscriptions.pricing import round_money

from . import notifications, periods
from .exceptions import (
    BillingError,
    InvalidInvoiceTransition,
    InvoiceNotSendable,
    SkipSubscription,
)
from .models import ZERO, Invoice, InvoiceLine, InvoiceNumberSequence

logger = logging.getLogger(__name__)

Status = Invoice.Status

# The only place that says which status changes are legal (FR-5.6, REQUIREMENTS 7.2).
ALLOWED_TRANSITIONS = {
    Status.DRAFT: {Status.CONFIRMED, Status.CANCELLED},
    Status.CONFIRMED: {Status.PAID, Status.CANCELLED},
    Status.PAID: set(),
    Status.CANCELLED: set(),
}
TIMESTAMP_FIELD = {
    Status.CONFIRMED: "confirmed_at",
    Status.PAID: "paid_at",
    Status.CANCELLED: "cancelled_at",
}


def _require(actor, permission=Permission.MANAGE_INVOICES):
    # Checked here as well as in the views, so the services are safe from any entry point.
    if not has_permission(actor, permission):
        raise PermissionDenied


# --- The single status door --------------------------------------------------


def transition_invoice(invoice, to_status, *, actor=None):
    """Move an invoice to `to_status`; the only code that assigns status.

    Locks the row, checks the transition table, stamps the time and writes the
    audit entry in one transaction. M7 calls this with Status.PAID once a full
    payment is recorded. `actor=None` is the system.
    """
    with transaction.atomic():
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if to_status not in ALLOWED_TRANSITIONS[locked.status]:
            raise InvalidInvoiceTransition(
                f"A {locked.get_status_display().lower()} invoice can't be "
                f"{Status(to_status).label.lower()}."
            )
        from_status = locked.status
        locked.status = to_status
        stamp = TIMESTAMP_FIELD[to_status]
        setattr(locked, stamp, timezone.now())
        locked.save(update_fields=["status", stamp])
        record_audit(
            actor=actor,
            action="invoice.status_changed",
            target=locked,
            from_status=from_status,
            to_status=to_status,
        )
    logger.info("Invoice %s: %s -> %s", locked.pk, from_status, to_status)
    return locked


def confirm_invoice(*, actor, invoice):
    """Draft -> Confirmed; amounts are fixed from here on (FR-5.5, FR-5.10)."""
    _require(actor)
    return transition_invoice(invoice, Status.CONFIRMED, actor=actor)


def cancel_invoice(*, actor, invoice):
    """Draft/Confirmed -> Cancelled. The period stays billed (BR-5, Open Item I)."""
    _require(actor)
    return transition_invoice(invoice, Status.CANCELLED, actor=actor)


# --- Generation (FR-5.1) -------------------------------------------------------


def _allocate_number():
    """Next sequential number. Must run inside a transaction: the counter row
    stays locked until it commits, and a rollback returns the number."""
    InvoiceNumberSequence.objects.get_or_create(pk=1)
    sequence = InvoiceNumberSequence.objects.select_for_update().get(pk=1)
    sequence.last_value += 1
    sequence.save(update_fields=["last_value"])
    return f"INV-{sequence.last_value:06d}"


def _require_due(subscription, today):
    """Raise SkipSubscription with the reason the run log shows (FR-5.9)."""
    if subscription.status == Subscription.Status.PAUSED:
        raise SkipSubscription("Paused subscriptions are not billed (BR-6).")
    if subscription.status != Subscription.Status.ACTIVE:
        raise SkipSubscription(
            f"The subscription is {subscription.get_status_display().lower()}; "
            "only active subscriptions are billed."
        )
    start = subscription.next_billing_date
    if start is None:
        raise SkipSubscription("The subscription has no next billing date.")
    if start > today:
        raise SkipSubscription(f"Not due until {start:%Y-%m-%d}.")
    if start > subscription.expiry_date:
        raise SkipSubscription(
            "The next period would start after the expiry date "
            f"({subscription.expiry_date:%Y-%m-%d})."
        )


def _already_billed(subscription, period_start):
    existing = Invoice.objects.filter(subscription=subscription, period_start=period_start).first()
    if existing is None:
        return None
    reason = f"This billing period has already been invoiced ({existing.number})."
    if existing.status == Status.CANCELLED:
        reason += " The invoice was cancelled; a cancelled period stays billed (BR-5)."
    return reason


def _invoice_line(subscription_line):
    """Copy one subscription line. The agreed unit price comes from the
    subscription; the tax rate comes from the product's tax now (BR-8, FR-5.4)."""
    tax_rate = subscription_line.product.tax.rate
    amount = round_money(subscription_line.unit_price * subscription_line.quantity)
    discount = ZERO  # M6 discounts are not available yet; see the M5 open items.
    description = subscription_line.product.name
    if subscription_line.variant is not None:
        variant = subscription_line.variant
        description += f" ({variant.dimension}: {variant.value})"
    return InvoiceLine(
        product=subscription_line.product,
        description=description,
        is_addon=subscription_line.is_addon,
        quantity=subscription_line.quantity,
        unit_price=subscription_line.unit_price,
        tax_rate=tax_rate,
        amount=amount,
        discount_amount=discount,
        tax_amount=round_money((amount - discount) * tax_rate / Decimal("100")),
    )


def generate_invoice(subscription, *, today, actor=None):
    """Create the Draft invoice for the subscription's next billing period.

    The caller holds the subscription row lock in an open transaction (the
    billing run does). Advances `next_billing_date` past the billed period.
    Raises SkipSubscription when the subscription must not be billed now, and
    BillingError when its data can't produce a correct invoice.
    """
    _require_due(subscription, today)
    plan = subscription.plan
    start, end, next_start = periods.billing_period(
        subscription.next_billing_date, plan.billing_period, subscription.start_date
    )
    reason = _already_billed(subscription, start)
    if reason:
        raise SkipSubscription(reason)
    source_lines = list(subscription.lines.select_related("product__tax", "variant"))
    if not source_lines:
        raise BillingError("The subscription has no lines to invoice.")
    lines = [_invoice_line(line) for line in source_lines]
    untaxed = sum((line.amount for line in lines), ZERO)
    discount = sum((line.discount_amount for line in lines), ZERO)
    tax = sum((line.tax_amount for line in lines), ZERO)
    try:
        with transaction.atomic():  # savepoint: a duplicate undoes only this insert
            invoice = Invoice.objects.create(
                number=_allocate_number(),
                subscription=subscription,
                customer=subscription.customer,
                customer_email=subscription.customer.user.email,
                plan_name=plan.name,
                payment_terms_name=subscription.payment_terms.name,
                period_start=start,
                period_end=end,
                invoice_date=today,
                due_date=today + timedelta(days=subscription.payment_terms.days),
                untaxed_amount=untaxed,
                discount_amount=discount,
                tax_amount=tax,
                total=untaxed - discount + tax,
            )
    except IntegrityError:
        # The unique (subscription, period_start) constraint is authoritative:
        # a parallel run got there first (FR-5.3).
        reason = _already_billed(subscription, start)
        if reason is None:
            raise
        raise SkipSubscription(reason) from None
    for line in lines:
        line.invoice = invoice
    InvoiceLine.objects.bulk_create(lines)
    subscription.next_billing_date = next_start
    subscription.save(update_fields=["next_billing_date", "updated_at"])
    record_audit(actor=actor, action="invoice.created", target=invoice)
    logger.info("Invoice %s created for subscription %s", invoice.pk, subscription.pk)
    return invoice


# --- Delivery (FR-5.5) -----------------------------------------------------------


def send_invoice(*, actor, invoice):
    """Email the invoice to the customer. Returns True when it was handed to the
    mail server. A delivery failure never changes the invoice's status or
    amounts; it is logged and shown as "Failed, retry needed" (FR-10.4)."""
    _require(actor)
    invoice = Invoice.objects.select_related("subscription").get(pk=invoice.pk)
    if invoice.status not in (Status.CONFIRMED, Status.PAID):
        raise InvoiceNotSendable("Only confirmed or paid invoices can be emailed.")
    try:
        notifications.send_invoice_email(invoice)
    except OSError:
        logger.exception("Invoice email for invoice %s failed", invoice.pk)
        delivered, email_status, emailed_at = False, Invoice.EmailStatus.FAILED, None
    else:
        delivered, email_status, emailed_at = True, Invoice.EmailStatus.SENT, timezone.now()
    changes = {"email_status": email_status}
    if emailed_at:
        changes["emailed_at"] = emailed_at
    Invoice.objects.filter(pk=invoice.pk).update(**changes)
    record_audit(
        actor=actor,
        action="invoice.emailed" if delivered else "invoice.email_failed",
        target=invoice,
    )
    return delivered
