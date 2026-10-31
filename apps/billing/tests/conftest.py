import pytest

from apps.accounts.tests.factories import AdminFactory, CustomerFactory, StaffFactory
from apps.billing import notifications


@pytest.fixture
def admin_user(db):
    return AdminFactory(email="admin@example.com")


@pytest.fixture
def staff_user(db):
    return StaffFactory(email="staff@example.com")


@pytest.fixture
def customer(db):
    return CustomerFactory(user__email="cust@example.com")


@pytest.fixture
def customer_user(customer):
    return customer.user


@pytest.fixture
def other_customer(db):
    return CustomerFactory(user__email="other@example.com")


@pytest.fixture(autouse=True)
def plain_http_settings(settings):
    """Tests must not depend on the developer's .env."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False


@pytest.fixture(autouse=True)
def sent_invoices(monkeypatch):
    """Record invoice emails instead of sending them."""
    sent = []
    monkeypatch.setattr(notifications, "send_invoice_email", sent.append)
    return sent
