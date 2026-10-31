import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import User
from apps.accounts.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
    scope_to_customer,
)

from .factories import PASSWORD, CustomerFactory

pytestmark = pytest.mark.django_db

ADMIN_ONLY = {
    Permission.CREATE_STAFF,
    Permission.MANAGE_USERS,
    Permission.MANAGE_CATALOG,
    Permission.MANAGE_TAXES_AND_PAYMENT_TERMS,
    Permission.CREATE_DISCOUNT_RULES,
    Permission.MANAGE_QUOTATION_TEMPLATES,
}
INTERNAL_SHARED = {
    Permission.USE_QUOTATION_TEMPLATES,
    Permission.MANAGE_SUBSCRIPTIONS,
    Permission.ACCEPT_QUOTATION,
    Permission.RUN_BILLING,
    Permission.MANAGE_INVOICES,
    Permission.RECORD_PAYMENTS,
    Permission.VIEW_DASHBOARD,
}
CUSTOMER_ONLY = {
    Permission.ACCESS_CUSTOMER_PORTAL,
    Permission.MANAGE_OWN_SUBSCRIPTIONS,
    Permission.ACCEPT_OWN_QUOTATION,
    Permission.VIEW_OWN_INVOICES,
    Permission.VIEW_OWN_PAYMENTS,
}


def test_admin_permissions_match_matrix():
    assert ROLE_PERMISSIONS[User.Role.ADMIN] == ADMIN_ONLY | INTERNAL_SHARED


def test_staff_permissions_match_matrix():
    assert ROLE_PERMISSIONS[User.Role.STAFF] == INTERNAL_SHARED


def test_customer_permissions_match_matrix():
    assert ROLE_PERMISSIONS[User.Role.CUSTOMER] == CUSTOMER_ONLY


def test_every_permission_is_assigned_to_some_role():
    assigned = set().union(*ROLE_PERMISSIONS.values())
    assert assigned == set(Permission)


def test_default_deny_for_anonymous_inactive_and_unknown_role(admin_user, client):
    from django.contrib.auth.models import AnonymousUser

    assert not has_permission(AnonymousUser(), Permission.VIEW_DASHBOARD)
    admin_user.is_active = False
    assert not has_permission(admin_user, Permission.VIEW_DASHBOARD)
    admin_user.is_active = True
    admin_user.role = "unknown"
    assert not has_permission(admin_user, Permission.VIEW_DASHBOARD)


@pytest.mark.parametrize(
    "name", ["internal_home", "user_management", "staff_create", "portal_home", "portal_account"]
)
def test_anonymous_is_sent_to_sign_in(client, name):
    response = client.get(reverse(f"accounts:{name}"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_customer_cannot_reach_internal_routes(client, customer_user):
    client.force_login(customer_user)
    for name in ["internal_home", "user_management", "staff_create"]:
        assert client.get(reverse(f"accounts:{name}")).status_code == 403


def test_staff_cannot_reach_user_management(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("accounts:internal_home")).status_code == 200
    assert client.get(reverse("accounts:user_management")).status_code == 403
    assert client.get(reverse("accounts:staff_create")).status_code == 403


def test_internal_roles_cannot_reach_customer_portal(client, admin_user, staff_user):
    for user in (admin_user, staff_user):
        client.force_login(user)
        assert client.get(reverse("accounts:portal_home")).status_code == 403


def test_user_management_link_visible_to_admin_only(client, admin_user, staff_user):
    url = reverse("accounts:user_management")
    client.force_login(admin_user)
    assert url in client.get(reverse("accounts:internal_home")).content.decode()
    client.force_login(staff_user)
    assert url not in client.get(reverse("accounts:internal_home")).content.decode()


def test_admin_creates_staff_via_ui(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("accounts:staff_create"),
        {"email": "New.Staff@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 302
    created = User.objects.get(email="new.staff@example.com")
    assert created.role == User.Role.STAFF
    assert created.check_password(PASSWORD)


def test_admin_created_staff_can_sign_in(client, admin_user):
    services.create_staff_account(actor=admin_user, email="s@example.com", password=PASSWORD)
    response = client.post(
        reverse("accounts:login"), {"username": "s@example.com", "password": PASSWORD}
    )
    assert response.url == reverse("accounts:internal_home")


def test_duplicate_email_rule_applies_to_staff_creation(client, admin_user, customer_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("accounts:staff_create"),
        {"email": "CUST@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 200
    assert User.objects.filter(email__iexact="cust@example.com").count() == 1


def test_staff_cannot_create_staff_by_direct_post(client, staff_user):
    client.force_login(staff_user)
    response = client.post(
        reverse("accounts:staff_create"),
        {"email": "x@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 403
    assert not User.objects.filter(email="x@example.com").exists()


def test_customer_cannot_create_staff_by_direct_post(client, customer_user):
    client.force_login(customer_user)
    response = client.post(
        reverse("accounts:staff_create"),
        {"email": "x@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 403
    assert not User.objects.filter(email="x@example.com").exists()


@pytest.mark.parametrize("actor_fixture", ["staff_user", "customer_user"])
def test_service_enforces_admin_only(request, actor_fixture):
    actor = request.getfixturevalue(actor_fixture)
    with pytest.raises(PermissionDenied):
        services.create_staff_account(actor=actor, email="x@example.com", password=PASSWORD)
    assert not User.objects.filter(email="x@example.com").exists()


def test_create_superuser_makes_admin_role():
    admin = User.objects.create_superuser("root@example.com", PASSWORD)
    assert admin.role == User.Role.ADMIN
    assert admin.is_staff and admin.is_superuser


def test_database_rejects_invalid_role():
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("bad@example.com", PASSWORD, role="owner")


def test_scope_to_customer_returns_only_own_records(customer_user):
    from apps.accounts.models import Customer

    other = CustomerFactory(user__email="other@example.com")
    own = Customer.objects.get(user=customer_user)
    scoped = scope_to_customer(Customer.objects.all(), customer_user, lookup="user__customer")
    assert list(scoped) == [own]
    assert other not in scoped


def test_scope_to_customer_denies_non_customers(admin_user, staff_user):
    from apps.accounts.models import Customer

    for user in (admin_user, staff_user):
        with pytest.raises(PermissionDenied):
            scope_to_customer(Customer.objects.all(), user, lookup="user__customer")
