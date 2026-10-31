from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.catalog import services
from apps.catalog.exceptions import StaleVariantData
from apps.catalog.models import Product, ProductVariant

from .factories import ProductFactory, ProductVariantFactory, TaxFactory

pytestmark = pytest.mark.django_db


def product_fields(tax, **overrides):
    fields = {
        "name": "Support plan",
        "type": Product.Type.SERVICE,
        "sales_price": Decimal("2000.00"),
        "cost_price": Decimal("1200.00"),
        "notes": "",
        "tax": tax,
    }
    fields.update(overrides)
    return fields


def odoo_variant(**overrides):
    row = {"dimension": "Brand", "value": "Odoo", "price_adjustment": Decimal("560.00")}
    row.update(overrides)
    return row


def test_admin_creates_active_product_with_variant(admin_user, tax):
    product = services.create_product(
        actor=admin_user, fields=product_fields(tax), variants=[odoo_variant()]
    )
    product.refresh_from_db()
    assert product.is_archived is False
    assert product.tax == tax
    assert product.sales_price == Decimal("2000.00")
    variant = product.variants.get()
    assert (variant.dimension, variant.value) == ("Brand", "Odoo")
    assert variant.price_adjustment == Decimal("560.00")


def test_odoo_adjustment_gives_2560_before_tax_and_leaves_cost_unchanged(admin_user, tax):
    product = services.create_product(
        actor=admin_user, fields=product_fields(tax), variants=[odoo_variant()]
    )
    variant = ProductVariant.objects.select_related("product").get(product=product)
    assert variant.adjusted_sales_price == Decimal("2560.00")
    assert variant.product.sales_price == Decimal("2000.00")
    assert variant.product.cost_price == Decimal("1200.00")


def test_product_may_have_no_variants(admin_user, tax):
    product = services.create_product(actor=admin_user, fields=product_fields(tax), variants=[])
    assert product.variants.count() == 0


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_create_product(request, user_fixture, tax):
    actor = request.getfixturevalue(user_fixture)
    with pytest.raises(PermissionDenied):
        services.create_product(actor=actor, fields=product_fields(tax), variants=[])
    assert not Product.objects.exists()


def test_invalid_variant_leaves_no_partial_product(admin_user, tax):
    with pytest.raises(ValidationError):
        services.create_product(
            actor=admin_user,
            fields=product_fields(tax),
            variants=[odoo_variant(), odoo_variant(value="")],
        )
    assert not Product.objects.exists()
    assert not ProductVariant.objects.exists()


def test_service_rejects_negative_price(admin_user, tax):
    with pytest.raises(ValidationError):
        services.create_product(
            actor=admin_user,
            fields=product_fields(tax, sales_price=Decimal("-1.00")),
            variants=[],
        )
    assert not Product.objects.exists()


def test_update_changes_fields_and_tax(admin_user, tax):
    product = ProductFactory(tax=tax)
    other_tax = TaxFactory(name="Reduced", rate="5.00")
    services.update_product(
        actor=admin_user,
        product=product,
        fields=product_fields(
            other_tax,
            name="Renamed",
            type=Product.Type.GOODS,
            sales_price=Decimal("10.50"),
            cost_price=Decimal("4.25"),
            notes="Updated notes",
        ),
        variants=[],
    )
    product.refresh_from_db()
    assert product.name == "Renamed"
    assert product.type == Product.Type.GOODS
    assert product.sales_price == Decimal("10.50")
    assert product.cost_price == Decimal("4.25")
    assert product.notes == "Updated notes"
    assert product.tax == other_tax


def test_update_edits_in_place_adds_and_removes_variants(admin_user, tax):
    product = ProductFactory(tax=tax)
    kept = ProductVariantFactory(product=product, value="Odoo")
    removed = ProductVariantFactory(product=product, value="Other")
    services.update_product(
        actor=admin_user,
        product=product,
        fields=product_fields(tax),
        variants=[
            odoo_variant(id=kept.pk, price_adjustment=Decimal("600.00")),
            odoo_variant(value="New"),
        ],
    )
    variants = list(product.variants.all())
    assert [v.value for v in variants] == ["Odoo", "New"]
    assert variants[0].pk == kept.pk
    assert variants[0].price_adjustment == Decimal("600.00")
    assert not ProductVariant.objects.filter(pk=removed.pk).exists()


def test_update_with_foreign_or_stale_variant_id_changes_nothing(admin_user, tax):
    product = ProductFactory(tax=tax, name="Original")
    own = ProductVariantFactory(product=product)
    foreign = ProductVariantFactory()
    with pytest.raises(StaleVariantData):
        services.update_product(
            actor=admin_user,
            product=product,
            fields=product_fields(tax, name="Changed"),
            variants=[odoo_variant(id=foreign.pk)],
        )
    product.refresh_from_db()
    assert product.name == "Original"
    assert list(product.variants.all()) == [own]
    foreign.refresh_from_db()
    assert foreign.product_id != product.pk


def test_staff_cannot_update_product(staff_user, tax):
    product = ProductFactory(tax=tax, name="Original")
    with pytest.raises(PermissionDenied):
        services.update_product(
            actor=staff_user, product=product, fields=product_fields(tax), variants=[]
        )
    product.refresh_from_db()
    assert product.name == "Original"


def test_archive_is_idempotent_and_keeps_record(admin_user, tax):
    product = ProductFactory(tax=tax)
    ProductVariantFactory(product=product)
    services.archive_product(actor=admin_user, product=product)
    services.archive_product(actor=admin_user, product=product)
    product.refresh_from_db()
    assert product.is_archived is True
    assert product.variants.count() == 1


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_archive(request, user_fixture, tax):
    product = ProductFactory(tax=tax)
    with pytest.raises(PermissionDenied):
        services.archive_product(actor=request.getfixturevalue(user_fixture), product=product)
    product.refresh_from_db()
    assert product.is_archived is False


def test_admin_changes_are_logged_with_actor(admin_user, tax, caplog):
    caplog.set_level("INFO", logger="apps.catalog.services")
    product = services.create_product(actor=admin_user, fields=product_fields(tax), variants=[])
    services.archive_product(actor=admin_user, product=product)
    assert f"Product {product.pk} created by user {admin_user.pk}" in caplog.text
    assert f"Product {product.pk} archived by user {admin_user.pk}" in caplog.text
