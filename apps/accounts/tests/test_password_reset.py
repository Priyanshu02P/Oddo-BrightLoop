import logging
import re

import pytest
from django.core import mail
from django.urls import reverse

from .factories import PASSWORD

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "N3w!Passw0rd"


def request_reset(client, email):
    return client.post(reverse("accounts:password_reset"), {"email": email})


def reset_link():
    return re.search(r"https?://testserver(\S+)", mail.outbox[-1].body).group(1)


def submit_new_password(client, link, password=NEW_PASSWORD, confirm=None):
    response = client.get(link, follow=True)
    form_url = response.redirect_chain[-1][0]
    return client.post(
        form_url,
        {"new_password1": password, "new_password2": confirm or password},
    )


def test_same_public_response_for_known_and_unknown_email(client, customer_user):
    known = request_reset(client, "cust@example.com")
    unknown = request_reset(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 302
    assert known.url == unknown.url == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1


def test_reset_email_sent_to_registered_account(client, customer_user):
    request_reset(client, "CUST@example.com")
    assert mail.outbox[0].to == ["cust@example.com"]


def test_valid_link_sets_new_password(client, customer_user):
    request_reset(client, "cust@example.com")
    response = submit_new_password(client, reset_link())
    assert response.status_code == 302
    customer_user.refresh_from_db()
    assert customer_user.check_password(NEW_PASSWORD)
    assert not customer_user.check_password(PASSWORD)


def test_token_cannot_be_reused(client, customer_user):
    request_reset(client, "cust@example.com")
    link = reset_link()
    submit_new_password(client, link)
    response = client.get(link, follow=True)
    html = response.content.decode()
    assert "no longer valid" in html
    assert reverse("accounts:password_reset") in html
    customer_user.refresh_from_db()
    assert customer_user.check_password(NEW_PASSWORD)


def test_expired_token_rejected(client, customer_user, settings):
    request_reset(client, "cust@example.com")
    settings.PASSWORD_RESET_TIMEOUT = -1
    response = client.get(reset_link(), follow=True)
    assert "no longer valid" in response.content.decode()
    customer_user.refresh_from_db()
    assert customer_user.check_password(PASSWORD)


def test_weak_password_rejected_on_reset(client, customer_user):
    request_reset(client, "cust@example.com")
    response = submit_new_password(client, reset_link(), password="weakpass")
    assert response.status_code == 200
    assert "uppercase" in response.content.decode()
    customer_user.refresh_from_db()
    assert customer_user.check_password(PASSWORD)


def test_confirmation_mismatch_rejected(client, customer_user):
    request_reset(client, "cust@example.com")
    response = submit_new_password(client, reset_link(), confirm="Other!Passw0rd")
    assert response.status_code == 200
    customer_user.refresh_from_db()
    assert customer_user.check_password(PASSWORD)


def test_token_and_link_not_logged(client, customer_user, caplog):
    with caplog.at_level(logging.DEBUG):
        request_reset(client, "cust@example.com")
        link = reset_link()
        submit_new_password(client, link)
    token = link.rstrip("/").split("/")[-1]
    assert token not in caplog.text
    assert NEW_PASSWORD not in caplog.text
