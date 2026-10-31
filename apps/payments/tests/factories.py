from datetime import date
from decimal import Decimal

import factory

from apps.accounts.tests.factories import StaffFactory
from apps.billing.models import Invoice
from apps.billing.tests.factories import InvoiceFactory
from apps.payments.models import Payment

TODAY = date(2026, 7, 1)


def confirmed_invoice(**overrides):
    """An issued invoice of 2,300.00 waiting for payment."""
    return InvoiceFactory(status=Invoice.Status.CONFIRMED, **overrides)


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    reference = factory.Sequence(lambda n: f"T-PAY-{n:06d}")
    invoice = factory.SubFactory(InvoiceFactory, status=Invoice.Status.CONFIRMED)
    method = Payment.Method.BANK_TRANSFER
    amount = Decimal("2300.00")
    payment_date = TODAY
    status = Payment.Status.FAILED
    recorded_by = factory.SubFactory(StaffFactory)
