import pytest

from apps.accounts.tests.factories import AdminFactory, CustomerFactory, StaffFactory


@pytest.fixture
def admin_user(db):
    return AdminFactory(email="admin@example.com")


@pytest.fixture
def staff_user(db):
    return StaffFactory(email="staff@example.com")


@pytest.fixture
def customer_user(db):
    return CustomerFactory(user__email="cust@example.com").user


@pytest.fixture(autouse=True)
def plain_http_settings(settings):
    """Tests must not depend on the developer's .env (DEBUG off enables the
    HTTPS redirect and secure cookies)."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
