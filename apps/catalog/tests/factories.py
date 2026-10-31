from decimal import Decimal

import factory

from apps.catalog.models import PaymentTerm, Product, ProductVariant, Tax


class TaxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tax

    name = factory.Sequence(lambda n: f"Tax {n}")
    rate = Decimal("15.00")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    type = Product.Type.SERVICE
    sales_price = Decimal("2000.00")
    cost_price = Decimal("1200.00")
    tax = factory.SubFactory(TaxFactory)


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    dimension = "Brand"
    value = factory.Sequence(lambda n: f"Brand {n}")
    price_adjustment = Decimal("0.00")


class PaymentTermFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentTerm

    name = factory.Sequence(lambda n: f"Net {n * 15}")
    days = factory.Sequence(lambda n: n * 15)
