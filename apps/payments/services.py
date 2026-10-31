"""Payment writes (FR-7.1 to FR-7.4, FR-7.7, FR-7.9).

The invoice row is locked for the whole operation, so two submissions for the
same invoice run one after the other. The database still has the last word:
one Pending/Succeeded payment per invoice and one payment per idempotency key.
Invoice status only changes through billing.services.transition_invoice.
"""

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission
from apps.billing import services as billing
from apps.billing.models import Invoice

from . import providers
from .exceptions import (
    DuplicatePayment,
    InvalidPaymentDetails,
    InvoiceNotPayable,
    PaymentAmountMismatch,
    PaymentPending,
)
from .models import Payment, PaymentReferenceSequence

logger = logging.getLogger(__name__)

Status = Payment.Status


def _require(actor):
    # Checked here as well as in the views, so the services are safe from any entry point.
    if not has_permission(actor, Permission.RECORD_PAYMENTS):
        raise PermissionDenied


def mock_gateway_enabled():
    return settings.PAYMENT_MOCK_GATEWAY_ENABLED


def _allocate_reference():
    """Next sequential reference; runs inside the caller's transaction."""
    PaymentReferenceSequence.objects.get_or_create(pk=1)
    sequence = PaymentReferenceSequence.objects.select_for_update().get(pk=1)
    sequence.last_value += 1
    sequence.save(update_fields=["last_value"])
    return f"PAY-{sequence.last_value:06d}"


def _validate_details(method, payment_date, simulated_outcome):
    if method not in Payment.Method.values:
        raise InvalidPaymentDetails("Choose a valid payment method.")
    if method == Payment.Method.TEST_GATEWAY:
        if not mock_gateway_enabled():
            raise InvalidPaymentDetails("The test gateway is not available here.")
        if simulated_outcome not in providers.SimulatedOutcome.values:
            raise InvalidPaymentDetails("Choose the simulated gateway outcome.")
    if payment_date > timezone.localdate():
        raise InvalidPaymentDetails("The payment date can't be in the future.")


def _require_payable(invoice):
    if invoice.status == Invoice.Status.PAID:
        raise InvoiceNotPayable(f"Invoice {invoice.number} is already paid.")
    if invoice.status != Invoice.Status.CONFIRMED:
        raise InvoiceNotPayable(
            f"Invoice {invoice.number} is {invoice.get_status_display().lower()}; "
            "only confirmed invoices can be paid."
        )
    if invoice.payments.filter(status=Status.PENDING).exists():
        raise PaymentPending(
            f"A test-gateway payment for invoice {invoice.number} is still pending. "
            "Resolve it before recording another payment."
        )


def _require_exact_amount(invoice, amount):
    """Exact Decimal equality with the stored total; nothing is rounded (BR-7)."""
    if amount == invoice.total:
        return
    kind = "lower" if amount < invoice.total else "higher"
    raise PaymentAmountMismatch(
        f"The amount {amount:,.2f} is {kind} than the invoice total {invoice.total:,.2f}. "
        "The payment must equal the invoice total; partial payments are not accepted."
    )


def _replay(existing, *, invoice, method, amount, payment_date):
    """Same idempotency key: return the original outcome, never a second payment."""
    same = (existing.invoice_id, existing.method, existing.amount, existing.payment_date) == (
        invoice.pk,
        method,
        amount,
        payment_date,
    )
    if not same:
        raise DuplicatePayment(
            "This form was already submitted with different details. "
            "Reload the page to record a new payment."
        )
    return existing


def record_payment(
    *,
    actor,
    invoice,
    method,
    amount,
    payment_date,
    note="",
    idempotency_key=None,
    simulated_outcome=None,
):
    """Record one payment against one invoice and settle it on success.

    Returns the Payment (Succeeded, Failed or Pending). Only a Succeeded
    payment moves the invoice Confirmed -> Paid, in the same transaction.
    A repeated submission with the same `idempotency_key` returns the
    original payment instead of creating another.
    """
    _require(actor)
    _validate_details(method, payment_date, simulated_outcome)
    try:
        with transaction.atomic():
            locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
            if idempotency_key:
                existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
                if existing is not None:
                    return _replay(
                        existing,
                        invoice=locked,
                        method=method,
                        amount=amount,
                        payment_date=payment_date,
                    )
            _require_payable(locked)
            _require_exact_amount(locked, amount)
            reference = _allocate_reference()
            result = providers.provider_for(method, simulated_outcome).collect(
                payment_reference=reference, invoice=locked, amount=amount
            )
            payment = Payment.objects.create(
                reference=reference,
                invoice=locked,
                method=method,
                amount=amount,
                payment_date=payment_date,
                note=note,
                status=result.outcome,
                provider_reference=result.provider_reference,
                failure_reason=result.failure_reason,
                idempotency_key=idempotency_key or None,
                recorded_by=actor,
            )
            if payment.status == Status.SUCCEEDED:
                billing.transition_invoice(locked, Invoice.Status.PAID, actor=actor)
            record_audit(
                actor=actor, action="payment.recorded", target=payment, to_status=payment.status
            )
    except IntegrityError:
        # A concurrent request won the race the locks did not cover (e.g. the
        # same idempotency key on SQLite, which has no row locks).
        if idempotency_key and Payment.objects.filter(idempotency_key=idempotency_key).exists():
            raise DuplicatePayment("This payment was already submitted.") from None
        raise InvoiceNotPayable("This invoice was paid by another request.") from None
    log = logger.warning if payment.status == Status.FAILED else logger.info
    log("Payment %s for invoice %s: %s", payment.pk, invoice.pk, payment.status)
    return payment


def resolve_pending_payment(*, actor, payment, succeeded, reason=""):
    """Apply the gateway's late answer to a Pending payment (§5.5).

    The test-mode screen calls this to simulate the gateway's confirmation; a
    real provider's callback would call it too. Only a success settles the
    invoice.
    """
    _require(actor)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status != Status.PENDING:
            raise InvalidPaymentDetails(f"Payment {locked.reference} is no longer pending.")
        if succeeded and invoice.status != Invoice.Status.CONFIRMED:
            raise InvoiceNotPayable(
                f"Invoice {invoice.number} is {invoice.get_status_display().lower()}, so this "
                "payment can't settle it. Reconcile it with the customer manually."
            )
        from_status = locked.status
        locked.status = Status.SUCCEEDED if succeeded else Status.FAILED
        locked.failure_reason = "" if succeeded else (reason or "The gateway declined the payment.")
        locked.save(update_fields=["status", "failure_reason", "updated_at"])
        if succeeded:
            billing.transition_invoice(invoice, Invoice.Status.PAID, actor=actor)
        record_audit(
            actor=actor,
            action="payment.resolved",
            target=locked,
            from_status=from_status,
            to_status=locked.status,
        )
    logger.info("Payment %s resolved: %s", locked.pk, locked.status)
    return locked
