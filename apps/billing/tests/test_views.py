from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.billing import notifications
from apps.billing.models import BillingRun, Invoice
from apps.subscriptions.tests.factories import SubscriptionFactory

from .factories import InvoiceFactory, InvoiceLineFactory, due_subscription

pytestmark = pytest.mark.django_db

Status = Invoice.Status


def internal_urls(invoice, run):
    return [
        reverse("billing:invoice_list"),
        reverse("billing:invoice_detail", args=[invoice.pk]),
        reverse("billing:invoice_print", args=[invoice.pk]),
        reverse("billing:invoice_action", args=[invoice.pk, "confirm"]),
        reverse("billing:run_list"),
        reverse("billing:run_detail", args=[run.pk]),
    ]


def a_run():
    return BillingRun.objects.create(trigger=BillingRun.Trigger.MANUAL, run_date=date(2026, 7, 1))


# --- Access control ----------------------------------------------------------------


@pytest.mark.parametrize("user_fixture", ["admin_user", "staff_user"])
def test_internal_users_reach_every_billing_screen(request, client, user_fixture):
    client.force_login(request.getfixturevalue(user_fixture))
    for url in internal_urls(InvoiceLineFactory().invoice, a_run()):
        assert client.get(url).status_code == 200, url


def test_customers_are_denied_internal_billing_screens(client, customer):
    client.force_login(customer.user)
    invoice = InvoiceFactory(subscription__customer=customer, status=Status.CONFIRMED)
    for url in internal_urls(invoice, a_run()):
        assert client.get(url).status_code == 403, url
    assert client.post(reverse("billing:run_start")).status_code == 403
    assert (
        client.post(reverse("billing:invoice_action", args=[invoice.pk, "cancel"])).status_code
        == 403
    )
    invoice.refresh_from_db()
    assert invoice.status == Status.CONFIRMED
    assert not BillingRun.objects.filter(triggered_by=customer.user).exists()


def test_anonymous_users_are_sent_to_sign_in(client):
    for url in internal_urls(InvoiceFactory(), a_run()) + [reverse("portal_invoices:invoice_list")]:
        response = client.get(url)
        assert response.status_code == 302 and reverse("accounts:login") in response.url, url


def test_nav_shows_billing_to_internal_users_only(client, staff_user, customer_user):
    client.force_login(staff_user)
    home = client.get(reverse("accounts:internal_home")).content.decode()
    assert reverse("billing:invoice_list") in home and reverse("billing:run_list") in home
    client.force_login(customer_user)
    portal = client.get(reverse("accounts:portal_home")).content.decode()
    assert reverse("billing:invoice_list") not in portal
    assert reverse("portal_invoices:invoice_list") in portal


# --- Internal invoice screens -------------------------------------------------------


def test_list_filters_by_status_search_dates_and_overdue(client, staff_user):
    today = timezone.localdate()
    late = InvoiceFactory(
        status=Status.CONFIRMED,
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
    )
    due_today = InvoiceFactory(status=Status.CONFIRMED, invoice_date=today, due_date=today)
    paid_late = InvoiceFactory(
        status=Status.PAID,
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
    )
    client.force_login(staff_user)
    url = reverse("billing:invoice_list")

    def numbers(**params):
        return {invoice.number for invoice in client.get(url, params).context["page"]}

    assert numbers() == {late.number, due_today.number, paid_late.number}
    assert numbers(overdue="1") == {late.number}  # due today is not overdue; paid never is
    assert numbers(status="paid") == {paid_late.number}
    assert numbers(q=late.number) == {late.number}
    assert numbers(q=due_today.subscription.number) == {due_today.number}
    assert numbers(**{"from": today.isoformat()}) == {due_today.number}
    assert numbers(**{"to": "not-a-date"}) == {late.number, due_today.number, paid_late.number}


def test_list_is_paginated_and_query_count_is_fixed(
    client, staff_user, django_assert_max_num_queries
):
    for _ in range(30):
        InvoiceFactory()
    client.force_login(staff_user)
    with django_assert_max_num_queries(8):
        response = client.get(reverse("billing:invoice_list"))
    assert len(response.context["page"].object_list) == 25


def test_detail_shows_lines_totals_and_overdue_flag(client, staff_user):
    today = timezone.localdate()
    invoice = InvoiceLineFactory(
        invoice__status=Status.DRAFT,
        invoice__invoice_date=today - timedelta(days=40),
        invoice__due_date=today - timedelta(days=3),
    ).invoice
    client.force_login(staff_user)
    content = client.get(reverse("billing:invoice_detail", args=[invoice.pk])).content.decode()
    for text in [
        invoice.number,
        "2,300.00",
        "15.00%",
        "Overdue · 3 days",
        "Confirm invoice",
        "Cancel invoice",
    ]:
        assert text in content, text


def test_confirm_through_the_confirmation_page(client, staff_user):
    invoice = InvoiceFactory()
    client.force_login(staff_user)
    url = reverse("billing:invoice_action", args=[invoice.pk, "confirm"])
    page = client.get(url).content.decode()
    assert invoice.number in page and "2,300.00" in page  # names the invoice and total
    response = client.post(url)
    assert response.url == reverse("billing:invoice_detail", args=[invoice.pk])
    invoice.refresh_from_db()
    assert invoice.status == Status.CONFIRMED


def test_cancel_page_warns_the_period_stays_billed(client, staff_user):
    invoice = InvoiceFactory(status=Status.CONFIRMED)
    client.force_login(staff_user)
    url = reverse("billing:invoice_action", args=[invoice.pk, "cancel"])
    assert "billing period stays billed" in client.get(url).content.decode()
    client.post(url)
    invoice.refresh_from_db()
    assert invoice.status == Status.CANCELLED


def test_invalid_action_shows_a_message_and_changes_nothing(client, staff_user):
    invoice = InvoiceFactory(status=Status.PAID)
    client.force_login(staff_user)
    response = client.post(
        reverse("billing:invoice_action", args=[invoice.pk, "cancel"]), follow=True
    )
    assert "can&#x27;t be cancelled" in response.content.decode()
    invoice.refresh_from_db()
    assert invoice.status == Status.PAID


def test_unknown_action_is_404(client, staff_user):
    client.force_login(staff_user)
    assert (
        client.get(
            reverse("billing:invoice_action", args=[InvoiceFactory().pk, "regenerate"])
        ).status_code
        == 404
    )


def test_failed_email_is_reported_without_changing_the_invoice(client, staff_user, monkeypatch):
    invoice = InvoiceFactory(status=Status.CONFIRMED)

    def refuse(_invoice):
        raise OSError("down")

    monkeypatch.setattr(notifications, "send_invoice_email", refuse)
    client.force_login(staff_user)
    response = client.post(
        reverse("billing:invoice_action", args=[invoice.pk, "send"]), follow=True
    )
    content = response.content.decode()
    assert "could not be sent" in content and "Failed, retry needed" in content
    invoice.refresh_from_db()
    assert invoice.status == Status.CONFIRMED


def test_print_view_is_standalone_and_escaped(client, staff_user):
    line = InvoiceLineFactory(description="<b>Seat</b>")
    client.force_login(staff_user)
    content = client.get(reverse("billing:invoice_print", args=[line.invoice_id])).content.decode()
    assert "window.print()" in content and "&lt;b&gt;Seat&lt;/b&gt;" in content


def test_subscription_page_links_its_invoices(client, staff_user):
    invoice = InvoiceFactory()
    client.force_login(staff_user)
    url = reverse("subscriptions:subscription_detail", args=[invoice.subscription_id])
    assert reverse("billing:invoice_detail", args=[invoice.pk]) in client.get(url).content.decode()


# --- Billing runs ----------------------------------------------------------------------


def test_staff_run_billing_now_and_see_the_result_log(client, staff_user):
    subscription = due_subscription(
        next_billing_date=timezone.localdate(), start_date=timezone.localdate()
    )
    client.force_login(staff_user)
    response = client.post(reverse("billing:run_start"))
    run = BillingRun.objects.get()
    assert response.url == reverse("billing:run_detail", args=[run.pk])
    detail = client.get(response.url).content.decode()
    assert subscription.number in detail and Invoice.objects.get().number in detail
    assert "Billing run finished: 1 invoices created, 0 skipped, 0 failed." in detail


def test_a_paused_run_offers_to_continue(client, staff_user, settings):
    settings.BILLING_TIME_BUDGET_SECONDS = -1
    due_subscription(next_billing_date=timezone.localdate(), start_date=timezone.localdate())
    client.force_login(staff_user)
    detail = client.post(reverse("billing:run_start"), follow=True).content.decode()
    assert "Continue run" in detail and "paused to stay within the time limit" in detail
    settings.BILLING_TIME_BUDGET_SECONDS = 20
    client.post(reverse("billing:run_continue", args=[BillingRun.objects.get().pk]))
    assert BillingRun.objects.get().status == BillingRun.Status.COMPLETED
    assert Invoice.objects.count() == 1


def test_run_start_requires_post(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("billing:run_start")).status_code == 405


@pytest.mark.parametrize("header", [None, "Bearer wrong", "Bearer "])
def test_cron_is_closed_without_the_right_secret(client, settings, header):
    settings.CRON_SECRET = "s3cret"
    headers = {"Authorization": header} if header is not None else {}
    assert client.get(reverse("billing:billing_cron"), headers=headers).status_code == 403
    assert not BillingRun.objects.exists()


def test_cron_is_closed_when_no_secret_is_configured(client, settings):
    settings.CRON_SECRET = ""
    response = client.get(reverse("billing:billing_cron"), headers={"Authorization": "Bearer "})
    assert response.status_code == 403


def test_cron_runs_billing_with_the_secret(client, settings):
    settings.CRON_SECRET = "s3cret"
    due_subscription(next_billing_date=timezone.localdate(), start_date=timezone.localdate())
    response = client.get(
        reverse("billing:billing_cron"), headers={"Authorization": "Bearer s3cret"}
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1


# --- Customer portal ------------------------------------------------------------------------


def test_customer_sees_only_their_issued_invoices(client, customer, other_customer):
    mine = InvoiceFactory(subscription__customer=customer, status=Status.CONFIRMED)
    draft = InvoiceFactory(subscription__customer=customer, status=Status.DRAFT)
    theirs = InvoiceFactory(subscription__customer=other_customer, status=Status.CONFIRMED)
    client.force_login(customer.user)
    listed = {i.number for i in client.get(reverse("portal_invoices:invoice_list")).context["page"]}
    assert listed == {mine.number}
    for invoice in (theirs, draft):
        for name in ("invoice_detail", "invoice_print"):
            assert (
                client.get(reverse(f"portal_invoices:{name}", args=[invoice.pk])).status_code == 404
            )


def test_customer_views_and_prints_own_invoice_without_internal_actions(client, customer):
    invoice = InvoiceLineFactory(
        invoice__subscription=SubscriptionFactory(customer=customer)
    ).invoice
    Invoice.objects.filter(pk=invoice.pk).update(status=Status.CONFIRMED)
    client.force_login(customer.user)
    detail = client.get(
        reverse("portal_invoices:invoice_detail", args=[invoice.pk])
    ).content.decode()
    assert invoice.number in detail and "2,300.00" in detail
    for internal in ("Confirm invoice", "Cancel invoice", "Send by email", "Run billing"):
        assert internal not in detail
    assert (
        client.get(reverse("portal_invoices:invoice_print", args=[invoice.pk])).status_code == 200
    )


def test_internal_users_have_no_portal_invoices(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("portal_invoices:invoice_list")).status_code == 403


def test_money_values_on_invoices_are_decimals():
    invoice = InvoiceFactory()
    invoice.refresh_from_db()
    assert isinstance(invoice.total, Decimal)
