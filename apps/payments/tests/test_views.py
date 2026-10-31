from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.billing.tests.factories import InvoiceFactory
from apps.payments.models import Payment
from apps.subscriptions.tests.factories import SubscriptionFactory

from .factories import PaymentFactory, confirmed_invoice

pytestmark = pytest.mark.django_db


def form_data(target_invoice, **overrides):
    data = {
        "invoice": str(target_invoice.pk),
        "method": "bank_transfer",
        "amount": "2300.00",
        "payment_date": timezone.localdate().isoformat(),
        "note": "",
        "idempotency_key": "key-1",
    }
    data.update(overrides)
    return data


def internal_urls(payment):
    return [
        reverse("payments:payment_list"),
        reverse("payments:payment_create"),
        reverse("payments:payment_detail", args=[payment.pk]),
        reverse("payments:overdue_list"),
    ]


# --- Access control --------------------------------------------------------------------


@pytest.mark.parametrize("user_fixture", ["admin_user", "staff_user"])
def test_internal_users_reach_every_payment_screen(request, client, user_fixture):
    client.force_login(request.getfixturevalue(user_fixture))
    for url in internal_urls(PaymentFactory()):
        assert client.get(url).status_code == 200, url


def test_customers_cannot_view_or_record_payments(client, customer):
    invoice = confirmed_invoice(subscription__customer=customer)
    client.force_login(customer.user)
    for url in internal_urls(PaymentFactory(invoice=invoice)):
        assert client.get(url).status_code == 403, url
    response = client.post(
        reverse("payments:payment_create"), form_data(invoice, idempotency_key="x")
    )
    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CONFIRMED
    assert Payment.objects.count() == 1


def test_anonymous_users_are_sent_to_sign_in(client):
    for url in internal_urls(PaymentFactory()):
        response = client.get(url)
        assert response.status_code == 302 and reverse("accounts:login") in response.url


def test_nav_shows_payments_to_internal_users_only(client, staff_user, customer):
    client.force_login(staff_user)
    assert (
        reverse("payments:payment_list")
        in client.get(reverse("accounts:internal_home")).content.decode()
    )
    client.force_login(customer.user)
    assert (
        reverse("payments:payment_list")
        not in client.get(reverse("accounts:portal_home")).content.decode()
    )


# --- Recording ---------------------------------------------------------------------------


def test_staff_record_a_payment_and_the_invoice_becomes_paid(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    response = client.post(
        reverse("payments:payment_create"), form_data(invoice, note="Wire 4471"), follow=True
    )
    payment = Payment.objects.get()
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    assert (payment.note, payment.recorded_by) == ("Wire 4471", staff_user)
    assert f"Invoice {invoice.number} is now Paid." in response.content.decode()


def test_the_form_prefills_invoice_and_total(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    form = client.get(reverse("payments:payment_create"), {"invoice": invoice.pk}).context["form"]
    assert (form.initial["invoice"], form.initial["amount"]) == (invoice, Decimal("2300.00"))
    assert form.initial["idempotency_key"]


def test_only_payable_invoices_are_offered(client, staff_user):
    payable = confirmed_invoice()
    InvoiceFactory(status=Invoice.Status.DRAFT)
    PaymentFactory(status=Payment.Status.SUCCEEDED)  # its invoice is settled
    client.force_login(staff_user)
    choices = (
        client.get(reverse("payments:payment_create")).context["form"].fields["invoice"].queryset
    )
    assert list(choices) == [payable]


def test_a_partial_amount_is_refused_on_the_amount_field(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    response = client.post(reverse("payments:payment_create"), form_data(invoice, amount="1000.00"))
    assert response.status_code == 200
    assert "partial payments are not accepted" in response.context["form"].errors["amount"][0]
    assert 'value="key-1"' in response.content.decode()  # same submission key kept
    assert not Payment.objects.exists()


def test_an_invoice_paid_meanwhile_gets_a_clear_message(client, staff_user):
    invoice = confirmed_invoice()
    PaymentFactory(invoice=invoice, status=Payment.Status.SUCCEEDED)
    Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.PAID)
    client.force_login(staff_user)
    response = client.post(reverse("payments:payment_create"), form_data(invoice))
    assert "already paid" in response.context["form"].errors["invoice"][0]


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"invoice": ""}, "invoice"),
        ({"method": ""}, "method"),
        ({"method": "crypto"}, "method"),
        ({"amount": "abc"}, "amount"),
        ({"amount": "0"}, "amount"),
        ({"payment_date": ""}, "payment_date"),
        ({"payment_date": "2099-01-01"}, "payment_date"),
        ({"method": "test_gateway"}, "simulated_outcome"),
    ],
)
def test_invalid_input_is_reported_per_field(client, staff_user, overrides, field):
    client.force_login(staff_user)
    response = client.post(
        reverse("payments:payment_create"), form_data(confirmed_invoice(), **overrides)
    )
    assert field in response.context["form"].errors
    assert not Payment.objects.exists()


def test_a_double_submit_records_one_payment(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    first = client.post(reverse("payments:payment_create"), form_data(invoice))
    second = client.post(reverse("payments:payment_create"), form_data(invoice))
    assert first.url == second.url  # both land on the original payment
    assert Payment.objects.count() == 1


def test_forged_status_fields_are_ignored(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    client.post(
        reverse("payments:payment_create"),
        form_data(invoice, method="test_gateway", simulated_outcome="failure", status="succeeded"),
    )
    invoice.refresh_from_db()
    assert Payment.objects.get().status == Payment.Status.FAILED
    assert invoice.status == Invoice.Status.CONFIRMED


def test_test_mode_is_labelled_and_can_resolve_a_pending_payment(client, staff_user):
    invoice = confirmed_invoice()
    client.force_login(staff_user)
    detail = client.post(
        reverse("payments:payment_create"),
        form_data(invoice, method="test_gateway", simulated_outcome="delay"),
        follow=True,
    ).content.decode()
    assert "Test mode" in detail and "pending at the gateway" in detail
    payment = Payment.objects.get()
    client.post(reverse("payments:payment_resolve", args=[payment.pk, "success"]))
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID


def test_test_gateway_is_hidden_and_closed_when_disabled(client, staff_user, settings):
    settings.PAYMENT_MOCK_GATEWAY_ENABLED = False
    payment = PaymentFactory(method=Payment.Method.TEST_GATEWAY, status=Payment.Status.PENDING)
    client.force_login(staff_user)
    page = client.get(reverse("payments:payment_create")).content.decode()
    assert 'value="test_gateway"' not in page and "Simulated gateway outcome" not in page
    assert (
        client.post(reverse("payments:payment_resolve", args=[payment.pk, "success"])).status_code
        == 404
    )
    response = client.post(
        reverse("payments:payment_create"),
        form_data(confirmed_invoice(), method="test_gateway", simulated_outcome="success"),
    )
    assert "method" in response.context["form"].errors


# --- Lists ----------------------------------------------------------------------------------


def test_payment_list_filters(client, staff_user):
    cash = PaymentFactory(method=Payment.Method.CASH, status=Payment.Status.SUCCEEDED)
    card = PaymentFactory(
        method=Payment.Method.CARD, payment_date=timezone.localdate() - timedelta(days=40)
    )
    client.force_login(staff_user)
    url = reverse("payments:payment_list")

    def refs(**params):
        return {p.reference for p in client.get(url, params).context["page"]}

    assert refs() == {cash.reference, card.reference}
    assert refs(method="cash") == {cash.reference}
    assert refs(status="failed") == {card.reference}
    assert refs(q=cash.invoice.number) == {cash.reference}
    assert refs(**{"from": (timezone.localdate() - timedelta(days=5)).isoformat()}) == set()


def test_summary_shows_outstanding_overdue_and_paid(client, staff_user):
    today = timezone.localdate()
    confirmed_invoice(invoice_date=today - timedelta(days=40), due_date=today - timedelta(days=3))
    confirmed_invoice(invoice_date=today, due_date=today)
    client.force_login(staff_user)
    summary = client.get(reverse("payments:payment_list")).context["summary"]
    assert (summary["outstanding"]["count"], summary["outstanding"]["total"]) == (
        2,
        Decimal("4600.00"),
    )
    assert summary["overdue"]["count"] == 1


def test_overdue_list_shows_only_payable_late_invoices(client, staff_user):
    today = timezone.localdate()
    late = confirmed_invoice(
        invoice_date=today - timedelta(days=40), due_date=today - timedelta(days=9)
    )
    confirmed_invoice(invoice_date=today, due_date=today)  # due today: not overdue
    InvoiceFactory(
        status=Invoice.Status.CANCELLED,
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=9),
    )
    client.force_login(staff_user)
    response = client.get(reverse("payments:overdue_list"))
    rows = list(response.context["page"])
    assert rows == [late] and rows[0].days_late == 9
    assert f"?invoice={late.pk}" in response.content.decode()


def test_invoice_page_offers_record_payment_and_shows_history(client, staff_user):
    invoice = confirmed_invoice()
    failed = PaymentFactory(invoice=invoice)
    client.force_login(staff_user)
    page = client.get(reverse("billing:invoice_detail", args=[invoice.pk])).content.decode()
    assert f"{reverse('payments:payment_create')}?invoice={invoice.pk}" in page
    assert failed.reference in page


# --- Customer portal and cron -----------------------------------------------------------------


def test_customer_sees_how_their_paid_invoice_was_paid(client, customer, other_customer):
    mine = PaymentFactory(
        invoice__subscription=SubscriptionFactory(customer=customer),
        status=Payment.Status.SUCCEEDED,
    )
    Invoice.objects.filter(pk=mine.invoice_id).update(status=Invoice.Status.PAID)
    theirs = PaymentFactory(
        invoice__subscription=SubscriptionFactory(customer=other_customer),
        status=Payment.Status.SUCCEEDED,
    )
    Invoice.objects.filter(pk=theirs.invoice_id).update(status=Invoice.Status.PAID)
    client.force_login(customer.user)
    page = client.get(
        reverse("portal_invoices:invoice_detail", args=[mine.invoice_id])
    ).content.decode()
    assert mine.reference in page and "Record payment" not in page
    assert (
        client.get(reverse("portal_invoices:invoice_detail", args=[theirs.invoice_id])).status_code
        == 404
    )


@pytest.mark.parametrize("header", [None, "Bearer wrong"])
def test_dunning_cron_is_closed_without_the_secret(client, settings, header):
    settings.CRON_SECRET = "s3cret"
    headers = {"Authorization": header} if header else {}
    assert client.get(reverse("payments:dunning_cron"), headers=headers).status_code == 403


def test_dunning_cron_is_closed_when_no_secret_is_configured(client, settings):
    settings.CRON_SECRET = ""
    response = client.get(reverse("payments:dunning_cron"), headers={"Authorization": "Bearer "})
    assert response.status_code == 403


def test_dunning_cron_sends_due_reminders(client, settings, sent_reminders):
    settings.CRON_SECRET = "s3cret"
    today = timezone.localdate()
    confirmed_invoice(invoice_date=today - timedelta(days=40), due_date=today - timedelta(days=2))
    response = client.get(
        reverse("payments:dunning_cron"), headers={"Authorization": "Bearer s3cret"}
    )
    assert response.json()["sent"] == 1 and len(sent_reminders) == 1
