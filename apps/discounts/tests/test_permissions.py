import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.tests.factories import AdminFactory, CustomerFactory, StaffFactory
from apps.discounts import services
from apps.discounts.tests.factories import DiscountFactory


@pytest.mark.django_db
class TestDiscountPermissions:
    def test_admin_can_access_list(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        response = client.get(reverse("discounts:discount_list"))
        assert response.status_code == 200

    def test_admin_can_access_create(self, client):
        admin = AdminFactory()
        client.force_login(admin)
        response = client.get(reverse("discounts:discount_create"))
        assert response.status_code == 200

    def test_admin_can_access_detail_and_edit(self, client):
        admin = AdminFactory()
        discount = DiscountFactory(created_by=admin)
        client.force_login(admin)

        response = client.get(reverse("discounts:discount_detail", kwargs={"pk": discount.pk}))
        assert response.status_code == 200

        response = client.get(reverse("discounts:discount_edit", kwargs={"pk": discount.pk}))
        assert response.status_code == 200

    def test_staff_forbidden(self, client):
        staff = StaffFactory()
        discount = DiscountFactory()
        client.force_login(staff)

        assert client.get(reverse("discounts:discount_list")).status_code == 403
        assert client.get(reverse("discounts:discount_create")).status_code == 403
        assert (
            client.get(reverse("discounts:discount_detail", kwargs={"pk": discount.pk})).status_code
            == 403
        )
        assert (
            client.get(reverse("discounts:discount_edit", kwargs={"pk": discount.pk})).status_code
            == 403
        )

    def test_customer_forbidden(self, client):
        customer = CustomerFactory()
        discount = DiscountFactory()
        client.force_login(customer.user)

        assert client.get(reverse("discounts:discount_list")).status_code == 403
        assert client.get(reverse("discounts:discount_create")).status_code == 403
        assert (
            client.get(reverse("discounts:discount_detail", kwargs={"pk": discount.pk})).status_code
            == 403
        )
        assert (
            client.get(reverse("discounts:discount_edit", kwargs={"pk": discount.pk})).status_code
            == 403
        )

    def test_anonymous_redirected_to_login(self, client):
        discount = DiscountFactory()
        assert client.get(reverse("discounts:discount_list")).status_code == 302
        assert client.get(reverse("discounts:discount_create")).status_code == 302
        assert (
            client.get(reverse("discounts:discount_detail", kwargs={"pk": discount.pk})).status_code
            == 302
        )
        assert (
            client.get(reverse("discounts:discount_edit", kwargs={"pk": discount.pk})).status_code
            == 302
        )

    def test_service_level_permission_check(self):
        staff = StaffFactory()
        customer = CustomerFactory()
        discount = DiscountFactory()

        with pytest.raises(PermissionDenied):
            services.create_discount(actor=staff, data={})

        with pytest.raises(PermissionDenied):
            services.create_discount(actor=customer.user, data={})

        with pytest.raises(PermissionDenied):
            services.update_discount(actor=staff, discount=discount, data={})
