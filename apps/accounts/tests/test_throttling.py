import pytest
from django.urls import reverse

from apps.accounts.models import AuthAttempt, User

from .factories import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tight_limits(settings):
    settings.AUTH_THROTTLE = {
        "login": (3, 60),
        "signup": (2, 60),
        "password_reset": (2, 60),
    }


def test_login_is_throttled_after_repeated_failures(client, customer_user):
    url = reverse("accounts:login")
    for _ in range(3):
        assert (
            client.post(url, {"username": "cust@example.com", "password": "bad"}).status_code == 200
        )
    response = client.post(url, {"username": "cust@example.com", "password": PASSWORD})
    assert response.status_code == 429
    assert "Too many attempts" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_throttle_does_not_store_raw_email_or_ip(client, customer_user):
    client.post(reverse("accounts:login"), {"username": "cust@example.com", "password": "bad"})
    for attempt in AuthAttempt.objects.all():
        assert "cust@example.com" not in attempt.key
        assert "127.0.0.1" not in attempt.key


def test_signup_is_throttled(client):
    url = reverse("accounts:signup")
    for n in range(2):
        client.post(
            url, {"email": f"u{n}@example.com", "password1": PASSWORD, "password2": PASSWORD}
        )
    response = client.post(
        url, {"email": "u9@example.com", "password1": PASSWORD, "password2": PASSWORD}
    )
    assert response.status_code == 429
    assert not User.objects.filter(email="u9@example.com").exists()


def test_password_reset_is_throttled_with_safe_message(client):
    url = reverse("accounts:password_reset")
    for _ in range(2):
        assert client.post(url, {"email": "a@example.com"}).status_code == 302
    response = client.post(url, {"email": "a@example.com"})
    assert response.status_code == 429
    assert "Too many attempts" in response.content.decode()
