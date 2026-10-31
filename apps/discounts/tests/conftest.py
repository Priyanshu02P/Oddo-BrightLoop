import pytest

from apps.accounts.tests.factories import AdminFactory, CustomerFactory, StaffFactory


@pytest.fixture
def admin_user():
    return AdminFactory()


@pytest.fixture
def staff_user():
    return StaffFactory()


@pytest.fixture
def customer_user():
    return CustomerFactory()
