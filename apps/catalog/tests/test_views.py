from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Product, Tax

from .factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db

ODOO = {"dimension": "Brand", "value": "Odoo", "price_adjustment": "560"}


def form_data(product_tax, variants=(), initial=0, **overrides):
    data = {
        "name": "Support plan",
        "type": "service",
        "sales_price": "2000.00",
        "cost_price": "1200.00",
        "notes": "",
        "tax": str(product_tax.pk),
        "variants-TOTAL_FORMS": str(len(variants)),
        "variants-INITIAL_FORMS": str(initial),
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(variants):
        for key, value in row.items():
            data[f"variants-{index}-{key}"] = value
    data.update(overrides)
    return data


def catalog_urls(product):
    return [
        ("get", reverse("catalog:product_list")),
        ("get", reverse("catalog:product_create")),
        ("get", reverse("catalog:product_detail", args=[product.pk])),
        ("get", reverse("catalog:product_edit", args=[product.pk])),
        ("get", reverse("catalog:product_archive", args=[product.pk])),
    ]


# --- Permissions -----------------------------------------------------------


def test_admin_can_open_every_catalog_page(client, admin_user, tax):
    client.force_login(admin_user)
    for method, url in catalog_urls(ProductFactory(tax=tax)):
        assert getattr(client, method)(url).status_code == 200, url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_staff_and_customer_are_denied_every_catalog_page(request, client, user_fixture, tax):
    client.force_login(request.getfixturevalue(user_fixture))
    for method, url in catalog_urls(ProductFactory(tax=tax)):
        assert getattr(client, method)(url).status_code == 403, url


def test_anonymous_is_sent_to_sign_in(client, tax):
    for method, url in catalog_urls(ProductFactory(tax=tax)):
        response = getattr(client, method)(url)
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_direct_writes_by_non_admins_change_nothing(request, client, user_fixture, tax):
    product = ProductFactory(tax=tax, name="Original")
    client.force_login(request.getfixturevalue(user_fixture))
    responses = [
        client.post(reverse("catalog:product_create"), form_data(tax, name="Sneaky")),
        client.post(
            reverse("catalog:product_edit", args=[product.pk]),
            form_data(tax, name="Changed", variants=[ODOO]),
        ),
        client.post(reverse("catalog:product_archive", args=[product.pk])),
    ]
    assert [r.status_code for r in responses] == [403, 403, 403]
    product.refresh_from_db()
    assert (product.name, product.is_archived, product.variants.count()) == ("Original", False, 0)
    assert Product.objects.count() == 1


def test_catalog_nav_link_shown_to_admin_only(client, admin_user, staff_user):
    client.force_login(admin_user)
    url = reverse("catalog:product_list")
    assert url in client.get(reverse("accounts:internal_home")).content.decode()
    client.force_login(staff_user)
    assert url not in client.get(reverse("accounts:internal_home")).content.decode()


# --- Create ----------------------------------------------------------------


def test_admin_creates_product_with_variant(client, admin_user, tax):
    client.force_login(admin_user)
    response = client.post(
        reverse("catalog:product_create"), form_data(tax, notes="Internal", variants=[ODOO])
    )
    product = Product.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("catalog:product_detail", args=[product.pk])
    assert product.notes == "Internal"
    assert product.is_archived is False
    assert product.variants.get().price_adjustment == Decimal("560.00")

    detail = client.get(response.url).content.decode()
    assert "saved." in detail
    assert "2,560.00" in detail
    assert "+560.00" in detail


def test_blank_extra_variant_row_is_ignored(client, admin_user, tax):
    client.force_login(admin_user)
    blank = {"dimension": "", "value": "", "price_adjustment": ""}
    response = client.post(reverse("catalog:product_create"), form_data(tax, variants=[blank]))
    assert response.status_code == 302
    assert Product.objects.get().variants.count() == 0


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"type": ""}, "type"),
        ({"type": "subscription"}, "type"),
        ({"sales_price": ""}, "sales_price"),
        ({"sales_price": "12,5x"}, "sales_price"),
        ({"sales_price": "1.234"}, "sales_price"),
        ({"sales_price": "-5"}, "sales_price"),
        ({"cost_price": ""}, "cost_price"),
        ({"cost_price": "abc"}, "cost_price"),
        ({"tax": ""}, "tax"),
        ({"tax": "999999"}, "tax"),
    ],
)
def test_invalid_product_fields_are_rejected(client, admin_user, tax, overrides, field):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:product_create"), form_data(tax, **overrides))
    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert not Product.objects.exists()


@pytest.mark.parametrize(
    "row, field",
    [
        ({**ODOO, "dimension": ""}, "dimension"),
        ({**ODOO, "value": ""}, "value"),
        ({**ODOO, "price_adjustment": ""}, "price_adjustment"),
        ({**ODOO, "price_adjustment": "five"}, "price_adjustment"),
        ({**ODOO, "price_adjustment": "1.005"}, "price_adjustment"),
        ({**ODOO, "price_adjustment": "-10"}, "price_adjustment"),
    ],
)
def test_invalid_variant_rejects_whole_save(client, admin_user, tax, row, field):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:product_create"), form_data(tax, variants=[ODOO, row]))
    assert response.status_code == 200
    assert field in response.context["formset"].forms[1].errors
    assert not Product.objects.exists()


def test_invalid_submission_keeps_entered_values(client, admin_user, tax):
    client.force_login(admin_user)
    response = client.post(
        reverse("catalog:product_create"), form_data(tax, name="Keep me", cost_price="")
    )
    assert 'value="Keep me"' in response.content.decode()


def test_forged_fields_are_ignored(client, admin_user, tax):
    client.force_login(admin_user)
    client.post(
        reverse("catalog:product_create"),
        form_data(tax, is_archived="on", role="customer", adjusted_price="1"),
    )
    product = Product.objects.get()
    assert product.is_archived is False
    assert product.sales_price == Decimal("2000.00")


def test_create_page_explains_missing_taxes(client, admin_user):
    assert not Tax.objects.exists()
    client.force_login(admin_user)
    content = client.get(reverse("catalog:product_create")).content.decode()
    assert "No taxes are configured yet" in content


# --- List and detail -------------------------------------------------------


def test_list_shows_columns_and_both_statuses(client, admin_user, tax):
    active = ProductFactory(tax=tax, name="Active one")
    ProductVariantFactory.create_batch(2, product=active)
    ProductFactory(tax=tax, name="Old one", is_archived=True)
    client.force_login(admin_user)
    content = client.get(reverse("catalog:product_list")).content.decode()
    for text in ["Active one", "Old one", "Service", "2,000.00", "1,200.00", "VAT (15.00%)"]:
        assert text in content
    assert ">Active</span>" in content
    assert ">Archived</span>" in content


def test_list_status_filter(client, admin_user, tax):
    ProductFactory(tax=tax, name="Active one")
    ProductFactory(tax=tax, name="Old one", is_archived=True)
    client.force_login(admin_user)
    content = client.get(reverse("catalog:product_list"), {"status": "archived"}).content.decode()
    assert "Old one" in content
    assert "Active one" not in content


def test_list_is_paginated(client, admin_user, tax):
    ProductFactory.create_batch(30, tax=tax)
    client.force_login(admin_user)
    page = client.get(reverse("catalog:product_list")).context["page"]
    assert len(page.object_list) == 25
    assert page.paginator.num_pages == 2


def test_list_empty_state(client, admin_user):
    client.force_login(admin_user)
    assert "No products exist yet" in client.get(reverse("catalog:product_list")).content.decode()


def test_detail_without_variants_and_escaped_notes(client, admin_user, tax):
    product = ProductFactory(tax=tax, notes="<script>alert(1)</script>")
    client.force_login(admin_user)
    content = client.get(reverse("catalog:product_detail", args=[product.pk])).content.decode()
    assert "No variants are configured" in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "<script>alert(1)" not in content


def test_unknown_product_is_404(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("catalog:product_detail", args=[999999])).status_code == 404


# --- Edit ------------------------------------------------------------------


def test_admin_edits_product_and_variants(client, admin_user, tax):
    product = ProductFactory(tax=tax)
    kept = ProductVariantFactory(product=product, value="Odoo")
    dropped = ProductVariantFactory(product=product, value="Other")
    client.force_login(admin_user)
    data = form_data(
        tax,
        name="Renamed",
        sales_price="100.00",
        initial=2,
        variants=[
            {"id": kept.pk, **ODOO, "price_adjustment": "25.50"},
            {"id": dropped.pk, **ODOO, "value": "Other", "DELETE": "on"},
            {"dimension": "Edition", "value": "Pro", "price_adjustment": "0"},
        ],
    )
    response = client.post(reverse("catalog:product_edit", args=[product.pk]), data)
    assert response.status_code == 302
    product.refresh_from_db()
    assert product.name == "Renamed"
    assert [(v.pk == kept.pk, v.value, v.price_adjustment) for v in product.variants.all()] == [
        (True, "Odoo", Decimal("25.50")),
        (False, "Pro", Decimal("0.00")),
    ]
    detail = client.get(response.url).content.decode()
    assert "125.50" in detail


def test_edit_cannot_hijack_another_products_variant(client, admin_user, tax):
    product = ProductFactory(tax=tax)
    foreign = ProductVariantFactory(value="Foreign")
    client.force_login(admin_user)
    data = form_data(tax, initial=1, variants=[{"id": foreign.pk, **ODOO}])
    response = client.post(reverse("catalog:product_edit", args=[product.pk]), data)
    assert response.status_code == 200
    assert "changed by someone else" in response.content.decode()
    foreign.refresh_from_db()
    assert (foreign.product_id, foreign.value) != (product.pk, "Odoo")
    assert product.variants.count() == 0


# --- Archive ---------------------------------------------------------------


def test_archive_requires_confirmation(client, admin_user, tax):
    product = ProductFactory(tax=tax)
    client.force_login(admin_user)
    content = client.get(reverse("catalog:product_archive", args=[product.pk])).content.decode()
    assert "no longer be offered for new subscription lines" in content
    product.refresh_from_db()
    assert product.is_archived is False


def test_admin_archives_product_and_it_stays_visible(client, admin_user, tax):
    product = ProductFactory(tax=tax, name="Retired")
    client.force_login(admin_user)
    url = reverse("catalog:product_archive", args=[product.pk])
    assert client.post(url).status_code == 302
    assert client.post(url).status_code == 302
    product.refresh_from_db()
    assert product.is_archived is True
    assert "Retired" in client.get(reverse("catalog:product_list")).content.decode()
    detail = client.get(reverse("catalog:product_detail", args=[product.pk])).content.decode()
    assert ">Archived</span>" in detail
