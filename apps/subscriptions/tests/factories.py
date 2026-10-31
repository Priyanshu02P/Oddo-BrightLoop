from datetime import date

import factory

from apps.accounts.tests.factories import CustomerFactory
from apps.catalog.models import PaymentTerm
from apps.catalog.tests.factories import ProductFactory
from apps.plans.tests.factories import PlanFactory
from apps.subscriptions.models import (
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
)


class PaymentTermFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentTerm

    name = factory.Sequence(lambda n: f"Net {n}")
    days = 30


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    number = factory.Sequence(lambda n: f"TEST-{n:06d}")
    customer = factory.SubFactory(CustomerFactory)
    plan = factory.SubFactory(PlanFactory)
    payment_terms = factory.SubFactory(PaymentTermFactory)
    start_date = date(2026, 6, 1)
    expiry_date = date(2026, 12, 31)
    quotation_validity_days = 30


class SubscriptionLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionLine

    subscription = factory.SubFactory(SubscriptionFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
    unit_price = "2000.00"
    tax_rate = "15.00"
    amount = "2000.00"
    tax_amount = "300.00"


class QuotationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuotationTemplate

    name = factory.Sequence(lambda n: f"Template {n}")
    plan = factory.SubFactory(PlanFactory)
    validity_days = 14


class QuotationTemplateLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuotationTemplateLine

    template = factory.SubFactory(QuotationTemplateFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 2
