import pytest
from django.urls import reverse

from .factories import PASSWORD

pytestmark = pytest.mark.django_db

GENERIC_ERROR = "Please enter a correct email and password."


def login(client, email, password=PASSWORD):
    return client.post(reverse("accounts:login"), {"username": email, "password": password})


def test_admin_login_reaches_internal_app(client, admin_user):
    response = login(client, "admin@example.com")
    assert response.status_code == 302
    assert response.url == reverse("accounts:internal_home")


def test_staff_login_reaches_internal_app(client, staff_user):
    assert login(client, "staff@example.com").url == reverse("accounts:internal_home")


def test_customer_login_reaches_portal(client, customer_user):
    assert login(client, "cust@example.com").url == reverse("accounts:portal_home")


def test_email_login_is_case_insensitive(client, customer_user):
    assert login(client, "CUST@Example.COM").status_code == 302


def test_wrong_password_and_unknown_email_give_same_generic_error(client, customer_user):
    wrong_password = login(client, "cust@example.com", "Wrong!Pass123")
    unknown_email = login(client, "nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 200
    assert GENERIC_ERROR in wrong_password.content.decode()
    assert GENERIC_ERROR in unknown_email.content.decode()


def test_inactive_user_gets_generic_error(client, customer_user):
    customer_user.is_active = False
    customer_user.save()
    response = login(client, "cust@example.com")
    assert response.status_code == 200
    assert GENERIC_ERROR in response.content.decode()


def test_required_fields(client):
    assert login(client, "", "").status_code == 200


def test_logout_ends_session(client, customer_user):
    login(client, "cust@example.com")
    assert client.get(reverse("accounts:portal_home")).status_code == 200
    client.post(reverse("accounts:logout"))
    response = client.get(reverse("accounts:portal_home"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_logout_requires_post(client, customer_user):
    login(client, "cust@example.com")
    client.get(reverse("accounts:logout"))
    assert client.get(reverse("accounts:portal_home")).status_code == 200


def test_home_routes_by_role(client, customer_user):
    assert client.get(reverse("accounts:home")).url == reverse("accounts:login")
    login(client, "cust@example.com")
    assert client.get(reverse("accounts:home")).url == reverse("accounts:portal_home")
