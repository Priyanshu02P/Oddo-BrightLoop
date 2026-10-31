from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.accounts.models import AuditLog
from apps.billing import notifications, services
from apps.billing.exceptions import InvalidInvoiceTransition, InvoiceLocked, InvoiceNotSendable
from apps.billing.models import Invoice

from .factories import InvoiceFactory, InvoiceLineFactory

pytestmark = pytest.mark.django_db

Status = Invoice.Status


@pytest.mark.parametrize(
    "start, target",
    [
        (Status.DRAFT, Status.CONFIRMED),
        (Status.DRAFT, Status.CANCELLED),
        (Status.CONFIRMED, Status.PAID),  # the M7 payment path calls this
        (Status.CONFIRMED, Status.CANCELLED),
    ],
)
def test_allowed_transitions_are_applied_stamped_and_audited(staff_user, start, target):
    invoice = InvoiceFactory(status=start)
    moved = services.transition_invoice(invoice, target, actor=staff_user)
    assert moved.status == target
    assert getattr(moved, services.TIMESTAMP_FIELD[target]) is not None
    entry = AuditLog.objects.get(action="invoice.status_changed", target_id=invoice.pk)
    assert (entry.actor, entry.from_status, entry.to_status) == (staff_user, start, target)


@pytest.mark.parametrize(
    "start, target",
    [
        (Status.DRAFT, Status.PAID),
        (Status.PAID, Status.CANCELLED),
        (Status.PAID, Status.CONFIRMED),
        (Status.CANCELLED, Status.CONFIRMED),
        (Status.CANCELLED, Status.PAID),
        (Status.CONFIRMED, Status.DRAFT),
    ],
)
def test_invalid_transitions_are_rejected(start, target):
    invoice = InvoiceFactory(status=start)
    with pytest.raises(InvalidInvoiceTransition):
        services.transition_invoice(invoice, target)
    invoice.refresh_from_db()
    assert invoice.status == start
    assert not AuditLog.objects.filter(action="invoice.status_changed").exists()


def test_staff_confirm_and_cancel(staff_user):
    invoice = InvoiceFactory()
    assert services.confirm_invoice(actor=staff_user, invoice=invoice).status == Status.CONFIRMED
    assert services.cancel_invoice(actor=staff_user, invoice=invoice).status == Status.CANCELLED


@pytest.mark.parametrize("service", ["confirm_invoice", "cancel_invoice", "send_invoice"])
def test_customers_cannot_act_on_invoices(customer_user, service):
    invoice = InvoiceFactory(subscription__customer=customer_user.customer, status=Status.CONFIRMED)
    with pytest.raises(PermissionDenied):
        getattr(services, service)(actor=customer_user, invoice=invoice)


@pytest.mark.parametrize("status", [Status.CONFIRMED, Status.PAID, Status.CANCELLED])
def test_issued_invoice_amounts_are_immutable(status):
    invoice = InvoiceFactory(status=status)
    invoice.total = Decimal("1.00")
    with pytest.raises(InvoiceLocked):
        invoice.save()
    invoice.refresh_from_db()
    assert invoice.total == Decimal("2300.00")


def test_issued_invoice_lines_are_immutable():
    line = InvoiceLineFactory()
    services.transition_invoice(line.invoice, Status.CONFIRMED)
    line.unit_price = Decimal("1.00")
    with pytest.raises(InvoiceLocked):
        line.save()
    with pytest.raises(InvoiceLocked):
        line.delete()


def test_draft_amounts_can_still_change():
    invoice = InvoiceFactory()
    invoice.total = Decimal("10.00")
    invoice.save()
    assert Invoice.objects.get(pk=invoice.pk).total == Decimal("10.00")


def test_send_emails_the_customer_and_records_delivery(staff_user, sent_invoices):
    invoice = InvoiceFactory(status=Status.CONFIRMED)
    assert services.send_invoice(actor=staff_user, invoice=invoice) is True
    invoice.refresh_from_db()
    assert sent_invoices == [invoice]
    assert invoice.email_status == Invoice.EmailStatus.SENT
    assert invoice.emailed_at is not None
    assert AuditLog.objects.filter(action="invoice.emailed", target_id=invoice.pk).exists()


def test_email_failure_leaves_the_invoice_intact(staff_user, monkeypatch, caplog):
    invoice = InvoiceFactory(status=Status.CONFIRMED)

    def refuse(_invoice):
        raise ConnectionRefusedError("mail server down")

    monkeypatch.setattr(notifications, "send_invoice_email", refuse)
    assert services.send_invoice(actor=staff_user, invoice=invoice) is False
    invoice.refresh_from_db()
    assert (invoice.status, invoice.total) == (Status.CONFIRMED, Decimal("2300.00"))
    assert invoice.email_status == Invoice.EmailStatus.FAILED
    assert "Invoice email for invoice" in caplog.text
    assert AuditLog.objects.filter(action="invoice.email_failed", target_id=invoice.pk).exists()


@pytest.mark.parametrize("status", [Status.DRAFT, Status.CANCELLED])
def test_unissued_invoices_cannot_be_emailed(staff_user, sent_invoices, status):
    with pytest.raises(InvoiceNotSendable):
        services.send_invoice(actor=staff_user, invoice=InvoiceFactory(status=status))
    assert sent_invoices == []
