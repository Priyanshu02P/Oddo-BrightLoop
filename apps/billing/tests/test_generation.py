from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import AuditLog
from apps.billing import services
from apps.billing.exceptions import BillingError, SkipSubscription
from apps.billing.models import Invoice
from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory, TaxFactory
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import PaymentTermFactory, SubscriptionLineFactory

from .factories import TODAY, InvoiceFactory, due_subscription

pytestmark = pytest.mark.django_db

Status = Invoice.Status


def generate(subscription, today=TODAY):
    return services.generate_invoice(subscription, today=today)


def test_invoice_is_prefilled_from_the_subscription():
    subscription = due_subscription(
        lines=0, payment_terms=PaymentTermFactory(name="Net 15", days=15)
    )
    SubscriptionLineFactory(
        subscription=subscription,
        product=ProductFactory(name="Cloud seat"),
        quantity=3,
        unit_price=Decimal("240.00"),
    )
    invoice = generate(subscription)

    assert invoice.status == Status.DRAFT
    assert invoice.number == "INV-000001"
    assert (invoice.subscription, invoice.customer) == (subscription, subscription.customer)
    assert invoice.customer_email == subscription.customer.user.email
    assert invoice.plan_name == subscription.plan.name
    assert (invoice.period_start, invoice.period_end) == (TODAY, date(2026, 7, 31))
    assert (invoice.invoice_date, invoice.due_date) == (TODAY, TODAY + timedelta(days=15))
    assert invoice.payment_terms_name == "Net 15"
    line = invoice.lines.get()
    assert (line.description, line.quantity, line.unit_price) == (
        "Cloud seat",
        3,
        Decimal("240.00"),
    )
    assert (line.amount, line.tax_rate, line.tax_amount) == (
        Decimal("720.00"),
        Decimal("15.00"),
        Decimal("108.00"),
    )
    assert (invoice.untaxed_amount, invoice.tax_amount, invoice.total) == (
        Decimal("720.00"),
        Decimal("108.00"),
        Decimal("828.00"),
    )


def test_each_line_carries_its_own_product_tax_rate():
    subscription = due_subscription(lines=0)
    standard = ProductFactory(tax=TaxFactory(rate="15.00"))
    reduced = ProductFactory(tax=TaxFactory(rate="5.00"))
    SubscriptionLineFactory(subscription=subscription, product=standard, unit_price="100.00")
    SubscriptionLineFactory(subscription=subscription, product=reduced, unit_price="100.00")
    invoice = generate(subscription)
    assert [line.tax_rate for line in invoice.lines.all()] == [Decimal("15.00"), Decimal("5.00")]
    assert invoice.tax_amount == Decimal("20.00")
    assert invoice.total == Decimal("220.00")


def test_tax_is_rounded_per_line_half_up():
    subscription = due_subscription(lines=0)
    product = ProductFactory(tax=TaxFactory(rate="15.00"))
    for _ in range(2):  # 0.15 * 0.03 = 0.0045 -> 0.00 per line, never summed first
        SubscriptionLineFactory(subscription=subscription, product=product, unit_price="0.03")
    SubscriptionLineFactory(subscription=subscription, product=product, unit_price="0.10")
    invoice = generate(subscription)
    assert [line.tax_amount for line in invoice.lines.all()] == [
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.02"),  # 0.015 rounds half-up
    ]
    assert isinstance(invoice.total, Decimal)


def test_variant_and_addon_are_described_on_the_line():
    subscription = due_subscription(lines=0)
    product = ProductFactory(name="Support")
    variant = ProductVariantFactory(product=product, dimension="Brand", value="Odoo")
    SubscriptionLineFactory(
        subscription=subscription, product=product, variant=variant, is_addon=True
    )
    line = generate(subscription).lines.get()
    assert line.description == "Support (Brand: Odoo)"
    assert line.is_addon


def test_generation_advances_the_next_billing_date():
    subscription = due_subscription()
    generate(subscription)
    subscription.refresh_from_db()
    assert subscription.next_billing_date == date(2026, 8, 1)


def test_creation_is_audited():
    invoice = generate(due_subscription())
    assert AuditLog.objects.filter(action="invoice.created", target_id=invoice.pk).exists()


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"status": Subscription.Status.PAUSED}, "Paused subscriptions are not billed"),
        ({"status": Subscription.Status.CLOSED}, "only active subscriptions are billed"),
        ({"next_billing_date": None}, "no next billing date"),
        ({"next_billing_date": date(2026, 7, 2)}, "Not due until 2026-07-02"),
        (
            {
                "next_billing_date": date(2026, 7, 1),
                "expiry_date": date(2026, 6, 30),
                "start_date": date(2026, 6, 1),
            },
            "after the expiry date",
        ),
    ],
)
def test_ineligible_subscriptions_are_skipped_with_a_reason(overrides, reason):
    subscription = due_subscription(**overrides)
    with pytest.raises(SkipSubscription, match=reason):
        generate(subscription)
    assert not Invoice.objects.exists()


def test_a_subscription_without_lines_fails_safely():
    with pytest.raises(BillingError, match="no lines"):
        generate(due_subscription(lines=0))
    assert not Invoice.objects.exists()


def test_the_same_period_is_never_invoiced_twice():
    subscription = due_subscription()
    first = generate(subscription)
    Subscription.objects.filter(pk=subscription.pk).update(next_billing_date=TODAY)
    subscription.refresh_from_db()
    with pytest.raises(SkipSubscription, match=f"already been invoiced \\({first.number}\\)"):
        generate(subscription)
    assert Invoice.objects.count() == 1


def test_a_cancelled_period_stays_billed():
    subscription = due_subscription()
    first = generate(subscription)
    services.transition_invoice(first, Status.CANCELLED)
    Subscription.objects.filter(pk=subscription.pk).update(next_billing_date=TODAY)
    subscription.refresh_from_db()
    with pytest.raises(SkipSubscription, match="cancelled period stays billed"):
        generate(subscription)
    assert Invoice.objects.count() == 1


def test_the_database_rejects_a_second_invoice_for_a_period():
    invoice = InvoiceFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        InvoiceFactory(subscription=invoice.subscription, period_start=invoice.period_start)


def test_a_lost_race_is_reported_as_skipped(monkeypatch):
    """A parallel run inserts after our pre-check; the unique constraint still wins."""
    subscription = due_subscription()
    InvoiceFactory(subscription=subscription, period_start=TODAY, period_end=date(2026, 7, 31))
    real, calls = services._already_billed, []

    def miss_the_first_check(*args):
        calls.append(args)
        return None if len(calls) == 1 else real(*args)

    monkeypatch.setattr(services, "_already_billed", miss_the_first_check)
    with pytest.raises(SkipSubscription, match="already been invoiced"):
        generate(subscription)
    assert Invoice.objects.count() == 1
    subscription.refresh_from_db()
    assert subscription.next_billing_date == TODAY  # nothing billed, so nothing advanced


def test_invoice_numbers_are_sequential():
    numbers = [generate(due_subscription()).number for _ in range(3)]
    assert numbers == ["INV-000001", "INV-000002", "INV-000003"]


def test_confirmed_totals_do_not_follow_later_catalog_changes():
    subscription = due_subscription()
    invoice = generate(subscription)
    services.transition_invoice(invoice, Status.CONFIRMED)
    line = subscription.lines.get()
    line.product.tax.rate = Decimal("25.00")
    line.product.tax.save()
    line.product.sales_price = Decimal("9999.00")
    line.product.save()
    invoice.refresh_from_db()
    assert (invoice.total, invoice.lines.get().tax_rate) == (Decimal("2300.00"), Decimal("15.00"))
