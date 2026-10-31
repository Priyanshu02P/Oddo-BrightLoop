from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import AuditLog
from apps.billing import services as billing
from apps.billing.models import Invoice
from apps.billing.tests.factories import InvoiceFactory
from apps.payments import services
from apps.payments.exceptions import (
    DuplicatePayment,
    InvalidPaymentDetails,
    InvoiceNotPayable,
    PaymentAmountMismatch,
    PaymentPending,
)
from apps.payments.models import Payment

from .factories import TODAY, PaymentFactory, confirmed_invoice

pytestmark = pytest.mark.django_db

TOTAL = Decimal("2300.00")
Status = Payment.Status


def pay(actor, invoice, **overrides):
    values = {
        "actor": actor,
        "invoice": invoice,
        "method": Payment.Method.BANK_TRANSFER,
        "amount": TOTAL,
        "payment_date": TODAY,
    }
    values.update(overrides)
    return services.record_payment(**values)


def test_exact_payment_settles_the_invoice_through_m5(staff_user):
    invoice = confirmed_invoice()
    payment = pay(staff_user, invoice, note="Wire 4471")
    invoice.refresh_from_db()
    assert (payment.status, payment.reference, payment.note) == (
        Status.SUCCEEDED,
        "PAY-000001",
        "Wire 4471",
    )
    assert (payment.invoice, payment.recorded_by) == (invoice, staff_user)
    assert isinstance(payment.amount, Decimal)
    assert invoice.status == Invoice.Status.PAID and invoice.paid_at is not None
    paid = AuditLog.objects.get(action="invoice.status_changed", target_id=invoice.pk)
    assert (paid.actor, paid.to_status) == (staff_user, "paid")
    assert AuditLog.objects.filter(action="payment.recorded", target_id=payment.pk).exists()


def test_admin_can_record_too(admin_user):
    assert pay(admin_user, confirmed_invoice()).status == Status.SUCCEEDED


@pytest.mark.parametrize(
    "amount, word", [("2299.99", "lower"), ("2300.01", "higher"), ("1150.00", "lower")]
)
def test_partial_and_overpayments_are_rejected(staff_user, amount, word):
    invoice = confirmed_invoice()
    with pytest.raises(PaymentAmountMismatch, match=f"is {word} than the invoice total 2,300.00"):
        pay(staff_user, invoice, amount=Decimal(amount))
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CONFIRMED
    assert not Payment.objects.exists()


@pytest.mark.parametrize(
    "status, message",
    [
        (Invoice.Status.DRAFT, "only confirmed invoices can be paid"),
        (Invoice.Status.CANCELLED, "only confirmed invoices can be paid"),
        (Invoice.Status.PAID, "already paid"),
    ],
)
def test_only_confirmed_invoices_are_payable(staff_user, status, message):
    with pytest.raises(InvoiceNotPayable, match=message):
        pay(staff_user, InvoiceFactory(status=status))
    assert not Payment.objects.exists()


def test_an_invoice_cannot_be_paid_twice(staff_user):
    invoice = confirmed_invoice()
    pay(staff_user, invoice)
    with pytest.raises(InvoiceNotPayable, match="already paid"):
        pay(staff_user, invoice, method=Payment.Method.CASH)
    assert Payment.objects.filter(status=Status.SUCCEEDED).count() == 1


def test_mock_failure_keeps_the_invoice_unpaid_and_allows_a_retry(staff_user):
    invoice = confirmed_invoice()
    failed = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="failure"
    )
    invoice.refresh_from_db()
    assert (failed.status, invoice.status) == (Status.FAILED, Invoice.Status.CONFIRMED)
    assert failed.provider_reference == f"TEST-{failed.reference}"
    retry = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="success"
    )
    invoice.refresh_from_db()
    assert (retry.status, invoice.status) == (Status.SUCCEEDED, Invoice.Status.PAID)


def test_mock_delay_is_pending_and_blocks_another_payment(staff_user):
    invoice = confirmed_invoice()
    pending = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="delay"
    )
    invoice.refresh_from_db()
    assert (pending.status, invoice.status) == (Status.PENDING, Invoice.Status.CONFIRMED)
    with pytest.raises(PaymentPending):
        pay(staff_user, invoice, method=Payment.Method.CASH)


def test_late_gateway_confirmation_settles_the_invoice(staff_user):
    invoice = confirmed_invoice()
    pending = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="delay"
    )
    resolved = services.resolve_pending_payment(actor=staff_user, payment=pending, succeeded=True)
    invoice.refresh_from_db()
    assert (resolved.status, invoice.status) == (Status.SUCCEEDED, Invoice.Status.PAID)
    with pytest.raises(InvalidPaymentDetails, match="no longer pending"):
        services.resolve_pending_payment(actor=staff_user, payment=pending, succeeded=False)


def test_late_gateway_decline_leaves_the_invoice_payable(staff_user):
    invoice = confirmed_invoice()
    pending = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="delay"
    )
    declined = services.resolve_pending_payment(actor=staff_user, payment=pending, succeeded=False)
    invoice.refresh_from_db()
    assert (declined.status, invoice.status) == (Status.FAILED, Invoice.Status.CONFIRMED)
    assert pay(staff_user, invoice).status == Status.SUCCEEDED


def test_a_late_success_cannot_settle_a_cancelled_invoice(staff_user):
    invoice = confirmed_invoice()
    pending = pay(
        staff_user, invoice, method=Payment.Method.TEST_GATEWAY, simulated_outcome="delay"
    )
    billing.transition_invoice(invoice, Invoice.Status.CANCELLED)
    with pytest.raises(InvoiceNotPayable, match="Reconcile"):
        services.resolve_pending_payment(actor=staff_user, payment=pending, succeeded=True)
    pending.refresh_from_db()
    assert pending.status == Status.PENDING


def test_the_same_submission_returns_the_original_payment(staff_user):
    invoice = confirmed_invoice()
    first = pay(staff_user, invoice, idempotency_key="k1")
    again = pay(staff_user, invoice, idempotency_key="k1")
    assert again.pk == first.pk
    assert Payment.objects.count() == 1


def test_a_reused_key_with_different_details_is_refused(staff_user):
    invoice = confirmed_invoice()
    pay(staff_user, invoice, idempotency_key="k1")
    with pytest.raises(DuplicatePayment):
        pay(staff_user, confirmed_invoice(), idempotency_key="k1")


def test_the_database_allows_one_open_or_successful_payment_per_invoice():
    payment = PaymentFactory(status=Status.SUCCEEDED)
    PaymentFactory(invoice=payment.invoice, status=Status.FAILED)  # attempts may pile up
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentFactory(invoice=payment.invoice, status=Status.PENDING)


def test_a_lost_race_is_reported_not_crashed(staff_user, monkeypatch):
    """A parallel request settles the invoice after our checks ran."""
    invoice = confirmed_invoice()
    PaymentFactory(invoice=invoice, status=Status.SUCCEEDED)  # bypasses the service
    monkeypatch.setattr(services, "_require_payable", lambda invoice: None)
    with pytest.raises(InvoiceNotPayable, match="another request"):
        pay(staff_user, invoice)


def test_a_failed_invoice_update_rolls_the_payment_back(staff_user, monkeypatch):
    invoice = confirmed_invoice()

    def broken(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(billing, "transition_invoice", broken)
    with pytest.raises(RuntimeError):
        pay(staff_user, invoice)
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CONFIRMED
    assert not Payment.objects.exists()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"method": "crypto"}, "valid payment method"),
        ({"payment_date": timezone.localdate() + timedelta(days=1)}, "in the future"),
        ({"method": Payment.Method.TEST_GATEWAY}, "simulated gateway outcome"),
    ],
)
def test_invalid_details_are_rejected(staff_user, overrides, message):
    with pytest.raises(InvalidPaymentDetails, match=message):
        pay(staff_user, confirmed_invoice(), **overrides)


def test_the_test_gateway_is_unavailable_when_disabled(staff_user, settings):
    settings.PAYMENT_MOCK_GATEWAY_ENABLED = False
    with pytest.raises(InvalidPaymentDetails, match="not available"):
        pay(
            staff_user,
            confirmed_invoice(),
            method=Payment.Method.TEST_GATEWAY,
            simulated_outcome="success",
        )


def test_customers_cannot_record_payments(customer):
    invoice = confirmed_invoice(subscription__customer=customer)
    with pytest.raises(PermissionDenied):
        pay(customer.user, invoice)
    with pytest.raises(PermissionDenied):
        services.resolve_pending_payment(
            actor=customer.user, payment=PaymentFactory(), succeeded=True
        )
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CONFIRMED
