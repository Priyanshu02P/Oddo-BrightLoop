from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.catalog import selectors, services
from apps.catalog.models import PaymentTerm, Tax

from .factories import PaymentTermFactory, TaxFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def tax_fields(**overrides):
    fields = {"name": "GST", "rate": Decimal("18.00")}
    fields.update(overrides)
    return fields


def term_fields(**overrides):
    fields = {"name": "Net 30", "days": 30}
    fields.update(overrides)
    return fields


# ---------------------------------------------------------------------------
# Service tests – Tax
# ---------------------------------------------------------------------------


def test_admin_can_create_tax(admin_user):
    tax = services.create_tax(actor=admin_user, fields=tax_fields())
    assert Tax.objects.filter(pk=tax.pk).exists()
    assert tax.name == "GST"
    assert tax.rate == Decimal("18.00")


def test_admin_can_update_tax(admin_user):
    tax = TaxFactory(name="Old", rate="5.00")
    updated = services.update_tax(
        actor=admin_user, tax=tax, fields=tax_fields(name="New", rate="9.00")
    )
    updated.refresh_from_db()
    assert updated.name == "New"
    assert updated.rate == Decimal("9.00")


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_create_tax(request, user_fixture):
    actor = request.getfixturevalue(user_fixture)
    with pytest.raises(PermissionDenied):
        services.create_tax(actor=actor, fields=tax_fields())
    assert not Tax.objects.exists()


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_update_tax(request, user_fixture):
    actor = request.getfixturevalue(user_fixture)
    tax = TaxFactory(name="Original")
    with pytest.raises(PermissionDenied):
        services.update_tax(actor=actor, tax=tax, fields=tax_fields(name="Hacked"))
    tax.refresh_from_db()
    assert tax.name == "Original"


def test_tax_decimal_precision_preserved(admin_user):
    tax = services.create_tax(actor=admin_user, fields=tax_fields(rate=Decimal("7.50")))
    tax.refresh_from_db()
    assert tax.rate == Decimal("7.50")


def test_create_tax_rejects_missing_name(admin_user):
    with pytest.raises(ValidationError):
        services.create_tax(actor=admin_user, fields=tax_fields(name=""))
    assert not Tax.objects.exists()


def test_create_tax_rejects_missing_rate(admin_user):
    with pytest.raises((ValidationError, TypeError, KeyError)):
        services.create_tax(actor=admin_user, fields={"name": "GST", "rate": None})


def test_create_tax_rejects_negative_rate(admin_user):
    with pytest.raises(ValidationError):
        services.create_tax(actor=admin_user, fields=tax_fields(rate=Decimal("-1.00")))
    assert not Tax.objects.exists()


def test_tax_creation_is_logged(admin_user, caplog):
    caplog.set_level("INFO", logger="apps.catalog.services")
    tax = services.create_tax(actor=admin_user, fields=tax_fields())
    assert f"Tax {tax.pk} created by user {admin_user.pk}" in caplog.text


def test_tax_update_is_logged(admin_user, caplog):
    caplog.set_level("INFO", logger="apps.catalog.services")
    tax = TaxFactory()
    services.update_tax(actor=admin_user, tax=tax, fields=tax_fields(name="Updated"))
    assert f"Tax {tax.pk} updated by user {admin_user.pk}" in caplog.text


# ---------------------------------------------------------------------------
# Service tests – PaymentTerm
# ---------------------------------------------------------------------------


def test_admin_can_create_payment_term(admin_user):
    term = services.create_payment_term(actor=admin_user, fields=term_fields())
    assert PaymentTerm.objects.filter(pk=term.pk).exists()
    assert term.name == "Net 30"
    assert term.days == 30


def test_admin_can_update_payment_term(admin_user):
    term = PaymentTermFactory(name="Old", days=15)
    updated = services.update_payment_term(
        actor=admin_user, payment_term=term, fields=term_fields(name="Net 60", days=60)
    )
    updated.refresh_from_db()
    assert updated.name == "Net 60"
    assert updated.days == 60


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_create_payment_term(request, user_fixture):
    actor = request.getfixturevalue(user_fixture)
    with pytest.raises(PermissionDenied):
        services.create_payment_term(actor=actor, fields=term_fields())
    assert not PaymentTerm.objects.exists()


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_cannot_update_payment_term(request, user_fixture):
    actor = request.getfixturevalue(user_fixture)
    term = PaymentTermFactory(name="Original", days=30)
    with pytest.raises(PermissionDenied):
        services.update_payment_term(
            actor=actor, payment_term=term, fields=term_fields(name="Hacked")
        )
    term.refresh_from_db()
    assert term.name == "Original"


def test_create_payment_term_rejects_missing_name(admin_user):
    with pytest.raises(ValidationError):
        services.create_payment_term(actor=admin_user, fields=term_fields(name=""))
    assert not PaymentTerm.objects.exists()


def test_create_payment_term_rejects_negative_days(admin_user):
    # PositiveIntegerField rejects negative values at full_clean
    with pytest.raises(ValidationError):
        services.create_payment_term(actor=admin_user, fields=term_fields(days=-1))
    assert not PaymentTerm.objects.exists()


def test_payment_term_creation_is_logged(admin_user, caplog):
    caplog.set_level("INFO", logger="apps.catalog.services")
    term = services.create_payment_term(actor=admin_user, fields=term_fields())
    assert f"PaymentTerm {term.pk} created by user {admin_user.pk}" in caplog.text


def test_payment_term_update_is_logged(admin_user, caplog):
    caplog.set_level("INFO", logger="apps.catalog.services")
    term = PaymentTermFactory()
    services.update_payment_term(
        actor=admin_user, payment_term=term, fields=term_fields(name="Immediate", days=0)
    )
    assert f"PaymentTerm {term.pk} updated by user {admin_user.pk}" in caplog.text


# ---------------------------------------------------------------------------
# Selector tests
# ---------------------------------------------------------------------------


def test_list_taxes_ordered_by_name(admin_user):
    TaxFactory(name="Zebra Tax", rate="5.00")
    TaxFactory(name="Alpha Tax", rate="10.00")
    names = list(selectors.list_taxes().values_list("name", flat=True))
    assert names == sorted(names)


def test_list_payment_terms_ordered_by_name(admin_user):
    PaymentTermFactory(name="Net 60", days=60)
    PaymentTermFactory(name="Immediate", days=0)
    names = list(selectors.list_payment_terms().values_list("name", flat=True))
    assert names == sorted(names)


def test_payment_term_exists_false_when_empty():
    assert selectors.payment_term_exists() is False


def test_payment_term_exists_true_when_present():
    PaymentTermFactory()
    assert selectors.payment_term_exists() is True


# ---------------------------------------------------------------------------
# View tests – Tax
# ---------------------------------------------------------------------------


def tax_urls(tax):
    return [
        ("get", reverse("catalog:tax_list")),
        ("get", reverse("catalog:tax_create")),
        ("get", reverse("catalog:tax_edit", args=[tax.pk])),
    ]


def test_admin_can_access_all_tax_pages(client, admin_user):
    client.force_login(admin_user)
    tax = TaxFactory()
    for method, url in tax_urls(tax):
        assert getattr(client, method)(url).status_code == 200, url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_get_403_on_tax_pages(request, client, user_fixture):
    tax = TaxFactory()
    client.force_login(request.getfixturevalue(user_fixture))
    for method, url in tax_urls(tax):
        assert getattr(client, method)(url).status_code == 403, url


def test_anonymous_redirected_to_login_for_tax_pages(client):
    tax = TaxFactory()
    for method, url in tax_urls(tax):
        response = getattr(client, method)(url)
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


def test_admin_creates_tax_via_post(client, admin_user):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:tax_create"), {"name": "VAT", "rate": "20.00"})
    assert response.status_code == 302
    assert response.url == reverse("catalog:tax_list")
    assert Tax.objects.filter(name="VAT", rate=Decimal("20.00")).exists()


def test_admin_create_tax_shows_success_flash(client, admin_user):
    client.force_login(admin_user)
    client.post(reverse("catalog:tax_create"), {"name": "GST", "rate": "18.00"})
    response = client.get(reverse("catalog:tax_list"))
    assert "saved" in response.content.decode().lower()


def test_admin_edits_tax_via_post(client, admin_user):
    tax = TaxFactory(name="Old", rate="5.00")
    client.force_login(admin_user)
    response = client.post(
        reverse("catalog:tax_edit", args=[tax.pk]), {"name": "New", "rate": "10.00"}
    )
    assert response.status_code == 302
    tax.refresh_from_db()
    assert tax.name == "New"
    assert tax.rate == Decimal("10.00")


@pytest.mark.parametrize(
    "data",
    [
        {"name": "", "rate": "18.00"},
        {"name": "GST", "rate": ""},
        {"name": "GST", "rate": "-5.00"},
    ],
)
def test_invalid_tax_form_returns_200_with_errors(client, admin_user, data):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:tax_create"), data)
    assert response.status_code == 200
    assert not Tax.objects.exists()


def test_tax_list_empty_state(client, admin_user):
    client.force_login(admin_user)
    content = client.get(reverse("catalog:tax_list")).content.decode()
    assert "No taxes configured yet" in content


def test_tax_list_shows_configured_taxes(client, admin_user):
    TaxFactory(name="GST", rate="18.00")
    client.force_login(admin_user)
    content = client.get(reverse("catalog:tax_list")).content.decode()
    assert "GST" in content
    assert "18.00" in content


# ---------------------------------------------------------------------------
# View tests – PaymentTerm
# ---------------------------------------------------------------------------


def payment_term_urls(term):
    return [
        ("get", reverse("catalog:payment_term_list")),
        ("get", reverse("catalog:payment_term_create")),
        ("get", reverse("catalog:payment_term_edit", args=[term.pk])),
    ]


def test_admin_can_access_all_payment_term_pages(client, admin_user):
    client.force_login(admin_user)
    term = PaymentTermFactory()
    for method, url in payment_term_urls(term):
        assert getattr(client, method)(url).status_code == 200, url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_non_admins_get_403_on_payment_term_pages(request, client, user_fixture):
    term = PaymentTermFactory()
    client.force_login(request.getfixturevalue(user_fixture))
    for method, url in payment_term_urls(term):
        assert getattr(client, method)(url).status_code == 403, url


def test_anonymous_redirected_to_login_for_payment_term_pages(client):
    term = PaymentTermFactory()
    for method, url in payment_term_urls(term):
        response = getattr(client, method)(url)
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


def test_admin_creates_payment_term_via_post(client, admin_user):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:payment_term_create"), {"name": "Net 30", "days": "30"})
    assert response.status_code == 302
    assert response.url == reverse("catalog:payment_term_list")
    assert PaymentTerm.objects.filter(name="Net 30", days=30).exists()


def test_admin_create_payment_term_shows_success_flash(client, admin_user):
    client.force_login(admin_user)
    client.post(reverse("catalog:payment_term_create"), {"name": "Net 30", "days": "30"})
    response = client.get(reverse("catalog:payment_term_list"))
    assert "saved" in response.content.decode().lower()


def test_admin_edits_payment_term_via_post(client, admin_user):
    term = PaymentTermFactory(name="Old", days=15)
    client.force_login(admin_user)
    response = client.post(
        reverse("catalog:payment_term_edit", args=[term.pk]), {"name": "New", "days": "60"}
    )
    assert response.status_code == 302
    term.refresh_from_db()
    assert term.name == "New"
    assert term.days == 60


@pytest.mark.parametrize(
    "data",
    [
        {"name": "", "days": "30"},
        {"name": "Net 30", "days": ""},
        {"name": "Net 30", "days": "-1"},
    ],
)
def test_invalid_payment_term_form_returns_200_with_errors(client, admin_user, data):
    client.force_login(admin_user)
    response = client.post(reverse("catalog:payment_term_create"), data)
    assert response.status_code == 200
    assert not PaymentTerm.objects.exists()


def test_payment_term_list_empty_state(client, admin_user):
    client.force_login(admin_user)
    content = client.get(reverse("catalog:payment_term_list")).content.decode()
    assert "No payment terms configured yet" in content


def test_payment_term_list_shows_configured_terms(client, admin_user):
    PaymentTermFactory(name="Net 30", days=30)
    client.force_login(admin_user)
    content = client.get(reverse("catalog:payment_term_list")).content.decode()
    assert "Net 30" in content
    assert "30" in content
