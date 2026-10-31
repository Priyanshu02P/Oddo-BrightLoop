from datetime import date
from decimal import Decimal

import factory

from apps.accounts.tests.factories import AdminFactory, CustomerFactory
from apps.catalog.tests.factories import ProductFactory
from apps.discounts.models import (
    Discount,
    DiscountProduct,
    DiscountRedemption,
    InvoiceDiscountSnapshot,
)


class DiscountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Discount

    name = factory.Sequence(lambda n: f"Discount {n}")
    discount_type = Discount.DiscountType.FIXED_AMOUNT
    value = Decimal("50.00")
    minimum_purchase_amount = None
    minimum_quantity = None
    start_date = date(2026, 1, 1)
    end_date = date(2026, 12, 31)
    usage_limit_per_customer = 3
    scope_type = Discount.ScopeType.WHOLE_SUBSCRIPTION
    is_active = True
    created_by = factory.SubFactory(AdminFactory)


class PercentageDiscountFactory(DiscountFactory):
    discount_type = Discount.DiscountType.PERCENTAGE
    value = Decimal("10.00")


class SelectedProductsDiscountFactory(DiscountFactory):
    class Meta:
        model = Discount
        skip_postgeneration_save = True

    scope_type = Discount.ScopeType.SELECTED_PRODUCTS

    @factory.post_generation
    def products(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for product in extracted:
                DiscountProduct.objects.create(discount=self, product=product)
        else:
            default_product = ProductFactory()
            DiscountProduct.objects.create(discount=self, product=default_product)


class DiscountProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DiscountProduct

    discount = factory.SubFactory(DiscountFactory)
    product = factory.SubFactory(ProductFactory)


class DiscountRedemptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DiscountRedemption

    discount = factory.SubFactory(DiscountFactory)
    customer = factory.SubFactory(CustomerFactory)
    usage_count = 1


class InvoiceDiscountSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceDiscountSnapshot

    invoice = factory.SubFactory("apps.billing.tests.factories.InvoiceFactory")
    discount = factory.SubFactory(DiscountFactory)
    discount_name = factory.LazyAttribute(lambda o: o.discount.name if o.discount else "Discount")
    discount_type = factory.LazyAttribute(
        lambda o: o.discount.discount_type if o.discount else "fixed"
    )
    discount_value = factory.LazyAttribute(
        lambda o: o.discount.value if o.discount else Decimal("50.00")
    )
    scope_type = factory.LazyAttribute(
        lambda o: o.discount.scope_type if o.discount else "whole_subscription"
    )
    application_order = 1
    amount_applied = Decimal("50.00")
    redemption_confirmed = False
