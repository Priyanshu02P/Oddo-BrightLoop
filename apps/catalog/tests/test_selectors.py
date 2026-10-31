import pytest

from apps.catalog import selectors

from .factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db


def test_new_subscription_lines_only_offer_active_products(tax):
    active = ProductFactory(tax=tax)
    ProductFactory(tax=tax, is_archived=True)
    assert list(selectors.list_products_for_new_subscription_lines()) == [active]


def test_list_counts_variants_and_filters_by_status(tax):
    active = ProductFactory(tax=tax, name="A")
    archived = ProductFactory(tax=tax, name="B", is_archived=True)
    ProductVariantFactory.create_batch(3, product=active)

    everything = list(selectors.list_products())
    assert everything == [active, archived]
    assert [p.variant_count for p in everything] == [3, 0]
    assert list(selectors.list_products(selectors.STATUS_ACTIVE)) == [active]
    assert list(selectors.list_products(selectors.STATUS_ARCHIVED)) == [archived]


def test_list_reads_tax_without_extra_queries(tax, django_assert_num_queries):
    for _ in range(5):
        ProductVariantFactory(product=ProductFactory(tax=tax))
    with django_assert_num_queries(1):
        rows = [(p.tax.name, p.variant_count) for p in selectors.list_products()]
    assert len(rows) == 5
