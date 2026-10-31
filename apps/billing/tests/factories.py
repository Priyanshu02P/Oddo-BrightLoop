from datetime import date
from decimal import Decimal

import factory

from apps.billing.models import Invoice, InvoiceLine
from apps.catalog.tests.factories import ProductFactory
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionLineFactory

TODAY = date(2026, 7, 1)


def due_subscription(*, lines=1, **overrides):
    """An Active monthly subscription whose next billing date is TODAY."""
    values = {
        "status": Subscription.Status.ACTIVE,
        "start_date": TODAY,
        "expiry_date": date(2026, 12, 31),
        "next_billing_date": TODAY,
    }
    values.update(overrides)
    subscription = SubscriptionFactory(**values)
    SubscriptionLineFactory.create_batch(lines, subscription=subscription)
    return subscription


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice

    number = factory.Sequence(lambda n: f"T-INV-{n:06d}")
    subscription = factory.SubFactory(SubscriptionFactory)
    customer = factory.SelfAttribute("subscription.customer")
    customer_email = factory.LazyAttribute(lambda o: o.customer.user.email)
    plan_name = "Plan"
    payment_terms_name = "Net 30"
    period_start = factory.Sequence(lambda n: date(2026, 1, 1).replace(year=2026 + n))
    period_end = factory.LazyAttribute(lambda o: o.period_start.replace(day=28))
    invoice_date = TODAY
    due_date = date(2026, 7, 31)
    untaxed_amount = Decimal("2000.00")
    tax_amount = Decimal("300.00")
    total = Decimal("2300.00")


class InvoiceLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceLine

    invoice = factory.SubFactory(InvoiceFactory)
    product = factory.SubFactory(ProductFactory)
    description = "Product"
    quantity = 1
    unit_price = Decimal("2000.00")
    tax_rate = Decimal("15.00")
    amount = Decimal("2000.00")
    tax_amount = Decimal("300.00")
