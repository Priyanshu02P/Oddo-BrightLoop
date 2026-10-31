from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import AdminFactory, CustomerFactory
from apps.catalog.tests.factories import ProductFactory
from apps.discounts.models import Discount
from apps.discounts.tests.factories import (
    DiscountFactory,
    DiscountRedemptionFactory,
    SelectedProductsDiscountFactory,
)


@pytest.mark.django_db
class TestDiscountViews:
    def test_list_view_and_filters(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        DiscountFactory(name="Alpha Promo", is_active=True)
        DiscountFactory(name="Beta Expired", is_active=False)

        # All
        res = client.get(reverse("discounts:discount_list"))
        assert res.status_code == 200
        assert "Alpha Promo" in res.content.decode()
        assert "Beta Expired" in res.content.decode()

        # Filter active
        res_active = client.get(reverse("discounts:discount_list") + "?is_active=1")
        assert "Alpha Promo" in res_active.content.decode()
        assert "Beta Expired" not in res_active.content.decode()

        # Search q
        res_search = client.get(reverse("discounts:discount_list") + "?q=Alpha")
        assert "Alpha Promo" in res_search.content.decode()
        assert "Beta Expired" not in res_search.content.decode()

    def test_detail_view(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        product = ProductFactory(name="Premium Cloud")
        discount = SelectedProductsDiscountFactory(
            name="Cloud Special",
            products=[product],
            minimum_purchase_amount=Decimal("300.00"),
            minimum_quantity=2,
        )
        customer = CustomerFactory()
        DiscountRedemptionFactory(discount=discount, customer=customer, usage_count=2)

        res = client.get(reverse("discounts:discount_detail", kwargs={"pk": discount.pk}))
        assert res.status_code == 200
        content = res.content.decode()
        assert "Cloud Special" in content
        assert "Premium Cloud" in content
        assert customer.user.email in content
        assert "2" in content

    def test_create_view_get_and_post_whole_subscription(self, client):
        admin = AdminFactory()
        client.force_login(admin)

        # GET
        res_get = client.get(reverse("discounts:discount_create"))
        assert res_get.status_code == 200

        # POST valid
        data = {
            "name": "Global 10%",
            "discount_type": "percentage",
            "value": "10.00",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "usage_limit_per_customer": 3,
            "scope_type": "whole_subscription",
            "is_active": "on",
        }
        res_post = client.post(reverse("discounts:discount_create"), data=data)
        assert res_post.status_code == 302
        created = Discount.objects.get(name="Global 10%")
        assert created.discount_type == Discount.DiscountType.PERCENTAGE
        assert created.value == Decimal("10.00")
        assert created.created_by == admin

    def test_create_view_selected_products_requires_products(self, client):
        admin = AdminFactory()
        client.force_login(admin)

        data = {
            "name": "Product Promo",
            "discount_type": "fixed",
            "value": "25.00",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "usage_limit_per_customer": 1,
            "scope_type": "selected_products",
            "products": [],  # Empty products
            "is_active": "on",
        }
        res = client.post(reverse("discounts:discount_create"), data=data)
        assert res.status_code == 200
        assert "At least one product must be selected" in res.content.decode()

    def test_create_view_selected_products_success(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        product = ProductFactory()

        data = {
            "name": "Product Promo",
            "discount_type": "fixed",
            "value": "25.00",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "usage_limit_per_customer": 1,
            "scope_type": "selected_products",
            "products": [product.pk],
            "is_active": "on",
        }
        res = client.post(reverse("discounts:discount_create"), data=data)
        assert res.status_code == 302
        created = Discount.objects.get(name="Product Promo")
        assert created.discount_products.filter(product=product).exists()

    def test_edit_view(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        discount = DiscountFactory(name="Old Name", value=Decimal("15.00"))

        res_get = client.get(reverse("discounts:discount_edit", kwargs={"pk": discount.pk}))
        assert res_get.status_code == 200
        assert "Old Name" in res_get.content.decode()

        data = {
            "name": "New Name",
            "discount_type": "fixed",
            "value": "20.00",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "usage_limit_per_customer": 2,
            "scope_type": "whole_subscription",
            "is_active": "on",
        }
        res_post = client.post(
            reverse("discounts:discount_edit", kwargs={"pk": discount.pk}), data=data
        )
        assert res_post.status_code == 302
        discount.refresh_from_db()
        assert discount.name == "New Name"
        assert discount.value == Decimal("20.00")
        assert discount.updated_by == admin

    def test_preview_endpoint(self, client):
        admin = AdminFactory()
        client.force_login(admin)

        # Fixed preview: $150 on $1000
        res = client.post(
            reverse("discounts:discount_preview"),
            data={
                "discount_type": "fixed",
                "value": "150.00",
                "example_amount": "1000.00",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["amount_applied"] == "150.00"
        assert data["remaining_amount"] == "850.00"

        # Percentage preview: 15% on $1000
        res = client.post(
            reverse("discounts:discount_preview"),
            data={
                "discount_type": "percentage",
                "value": "15.00",
                "example_amount": "1000.00",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["amount_applied"] == "150.00"
        assert data["remaining_amount"] == "850.00"

        # Invalid input
        res_err = client.post(
            reverse("discounts:discount_preview"),
            data={
                "discount_type": "unknown",
                "value": "abc",
            },
        )
        assert res_err.status_code == 400
