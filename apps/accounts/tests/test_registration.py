import logging

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.accounts import services
from apps.accounts.exceptions import EmailAlreadyRegistered
from apps.accounts.models import Customer, User

from .factories import PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def post_signup(client, **overrides):
    data = {"email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD}
    data.update(overrides)
    return client.post(reverse("accounts:signup"), data)


def test_signup_page_has_no_role_selector(client):
    html = client.get(reverse("accounts:signup")).content.decode().lower()
    assert 'name="role"' not in html


def test_successful_registration_creates_customer(client):
    response = post_signup(client)
    assert response.status_code == 302
    user = User.objects.get(email="new@example.com")
    assert user.role == User.Role.CUSTOMER
    assert Customer.objects.filter(user=user).exists()


def test_password_is_stored_hashed(client):
    post_signup(client)
    user = User.objects.get(email="new@example.com")
    assert user.password != PASSWORD
    assert PASSWORD not in user.password
    assert user.check_password(PASSWORD)
    assert not user.check_password("wrong")


@pytest.mark.parametrize("field", ["email", "password1", "password2"])
def test_missing_fields_rejected(client, field):
    response = post_signup(client, **{field: ""})
    assert response.status_code == 200
    assert not User.objects.exists()


def test_invalid_email_rejected(client):
    assert post_signup(client, email="not-an-email").status_code == 200
    assert not User.objects.exists()


def test_password_mismatch_rejected(client):
    response = post_signup(client, password2="Different!Pass1")
    assert response.status_code == 200
    assert "do not match" in response.content.decode()
    assert not User.objects.exists()


def test_weak_password_explains_unmet_rules(client):
    response = post_signup(client, password1="abc", password2="abc")
    html = response.content.decode()
    assert "more than 8 characters" in html
    assert "uppercase" in html
    assert "special character" in html
    assert not User.objects.exists()


def test_duplicate_email_same_case_rejected(client):
    UserFactory(email="dup@example.com")
    response = post_signup(client, email="dup@example.com")
    assert response.status_code == 200
    assert User.objects.count() == 1


def test_duplicate_email_different_case_rejected(client):
    UserFactory(email="dup@example.com")
    response = post_signup(client, email="DUP@Example.COM")
    assert response.status_code == 200
    assert User.objects.count() == 1


def test_email_is_normalized_to_lowercase(client):
    post_signup(client, email="  MiXed@Example.com ")
    assert User.objects.get().email == "mixed@example.com"


@pytest.mark.parametrize("role", ["admin", "Admin", "staff", "Staff"])
def test_forged_role_is_ignored(client, role):
    post_signup(client, role=role)
    assert User.objects.get(email="new@example.com").role == User.Role.CUSTOMER


def test_forged_privilege_fields_are_ignored(client):
    post_signup(client, is_staff="on", is_superuser="on", is_active="", role="admin")
    user = User.objects.get(email="new@example.com")
    assert user.role == User.Role.CUSTOMER
    assert not user.is_staff
    assert not user.is_superuser
    assert user.is_active


def test_database_rejects_case_insensitive_duplicate():
    User.objects.create_user("a@example.com", PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.bulk_create([User(email="A@EXAMPLE.COM", role="customer")])


def test_service_maps_lost_race_to_domain_error():
    """The service does no pre-check, so this is the lost-race path: the
    database constraint stops the second account and is mapped to a domain error."""
    services.register_customer(email="race@example.com", password=PASSWORD)
    with pytest.raises(EmailAlreadyRegistered):
        services.register_customer(email="RACE@example.com", password=PASSWORD)
    assert User.objects.count() == 1
    assert Customer.objects.count() == 1


def test_registration_does_not_log_password(client, caplog):
    with caplog.at_level(logging.DEBUG):
        post_signup(client)
    assert PASSWORD not in caplog.text
