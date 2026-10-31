import pytest

from apps.accounts.tests.factories import AdminFactory, CustomerFactory, StaffFactory
from apps.payments import notifications


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
def other_customer(db):
    return CustomerFactory(user__email="other@example.com")


@pytest.fixture(autouse=True)
def test_settings(settings):
    """Tests must not depend on the developer's .env."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
    settings.PAYMENT_MOCK_GATEWAY_ENABLED = True
    settings.DUNNING_CADENCE_DAYS = [1, 7, 14]
    settings.DUNNING_MAX_ATTEMPTS = 3


@pytest.fixture(autouse=True)
def sent_reminders(monkeypatch):
    """Record reminder emails instead of sending them."""
    sent = []

    def record(invoice, *, stage, days_past_due):
        sent.append((invoice.number, stage, days_past_due))

    monkeypatch.setattr(notifications, "send_overdue_reminder", record)
    return sent
