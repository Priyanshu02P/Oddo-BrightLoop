from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.tests.factories import ProductFactory
from apps.plans.tests.factories import PlanFactory
from apps.subscriptions.models import QuotationTemplate, Subscription

from .factories import (
    PaymentTermFactory,
    QuotationTemplateFactory,
    SubscriptionFactory,
    SubscriptionLineFactory,
)

pytestmark = pytest.mark.django_db

Status = Subscription.Status
FUTURE = date(2999, 1, 1)
PAST = date(2000, 1, 1)


def template_data(plan, product, **overrides):
    data = {
        "name": "Starter",
        "plan": str(plan.pk),
        "validity_days": "14",
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": str(product.pk),
        "lines-0-variant": "",
        "lines-0-quantity": "2",
    }
    data.update(overrides)
    return data


# --- Quotation templates: Admin only -------------------------------------------


def test_admin_manages_templates(client, admin_user):
    client.force_login(admin_user)
    template = QuotationTemplateFactory()
    for url in (
        reverse("subscriptions:template_list"),
        reverse("subscriptions:template_create"),
        reverse("subscriptions:template_edit", args=[template.pk]),
    ):
        assert client.get(url).status_code == 200, url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_staff_and_customers_cannot_reach_template_management(request, client, user_fixture):
    client.force_login(request.getfixturevalue(user_fixture))
    template = QuotationTemplateFactory()
    for url in (
        reverse("subscriptions:template_list"),
        reverse("subscriptions:template_create"),
        reverse("subscriptions:template_edit", args=[template.pk]),
    ):
        assert client.get(url).status_code == 403, url


def test_staff_cannot_post_a_template_directly(client, staff_user):
    client.force_login(staff_user)
    response = client.post(
        reverse("subscriptions:template_create"), template_data(PlanFactory(), ProductFactory())
    )
    assert response.status_code == 403
    assert QuotationTemplate.objects.count() == 0


def test_admin_creates_a_template_with_lines(client, admin_user):
    client.force_login(admin_user)
    plan, product = PlanFactory(), ProductFactory()
    response = client.post(reverse("subscriptions:template_create"), template_data(plan, product))
    assert response.status_code == 302
    template = QuotationTemplate.objects.get()
    assert (template.plan, template.validity_days) == (plan, 14)
    assert template.lines.get().quantity == 2


@pytest.mark.parametrize("override", [{"name": "   "}, {"validity_days": "0"}])
def test_invalid_templates_are_rejected(client, admin_user, override):
    client.force_login(admin_user)
    data = template_data(PlanFactory(), ProductFactory(), **override)
    response = client.post(reverse("subscriptions:template_create"), data)
    assert response.status_code == 200
    assert QuotationTemplate.objects.count() == 0


# --- Internal subscription screens ---------------------------------------------


@pytest.mark.parametrize("user_fixture", ["admin_user", "staff_user"])
def test_internal_users_see_subscriptions_and_status(request, client, user_fixture, customer):
    client.force_login(request.getfixturevalue(user_fixture))
    subscription = SubscriptionFactory(customer=customer, status=Status.PAUSED)
    listing = client.get(reverse("subscriptions:subscription_list"))
    detail = client.get(reverse("subscriptions:subscription_detail", args=[subscription.pk]))
    assert listing.status_code == detail.status_code == 200
    assert b"Paused" in listing.content and b"Paused" in detail.content


def test_list_filters_by_status_and_search(client, staff_user, customer):
    client.force_login(staff_user)
    SubscriptionFactory(customer=customer, status=Status.ACTIVE, number="TEST-AAA")
    SubscriptionFactory(status=Status.DRAFT, number="TEST-BBB")
    response = client.get(reverse("subscriptions:subscription_list"), {"status": "active"})
    assert b"TEST-AAA" in response.content and b"TEST-BBB" not in response.content
    response = client.get(reverse("subscriptions:subscription_list"), {"q": "cust@example"})
    assert b"TEST-AAA" in response.content and b"TEST-BBB" not in response.content


def test_customers_cannot_use_internal_screens(client, customer_user):
    client.force_login(customer_user)
    subscription = SubscriptionFactory()
    for url in (
        reverse("subscriptions:subscription_list"),
        reverse("subscriptions:subscription_create"),
        reverse("subscriptions:subscription_detail", args=[subscription.pk]),
    ):
        assert client.get(url).status_code == 403, url
    action = reverse("subscriptions:subscription_action", args=[subscription.pk, "send"])
    assert client.post(action).status_code == 403


def test_staff_create_a_subscription_from_a_template(client, staff_user, customer):
    client.force_login(staff_user)
    template = QuotationTemplateFactory(plan=PlanFactory())
    terms = PaymentTermFactory()
    response = client.post(
        reverse("subscriptions:subscription_create"),
        {
            "customer": customer.pk,
            "template": template.pk,
            "plan": "",
            "start_date": "2026-06-01",
            "expiry_date": "2026-12-31",
            "payment_terms": terms.pk,
            # Forged fields must be ignored.
            "status": "active",
            "number": "HACK-1",
        },
    )
    subscription = Subscription.objects.get()
    assert response.status_code == 302
    assert subscription.status == Status.DRAFT
    assert subscription.number == "SUB-000001"
    assert subscription.plan == template.plan


def test_subscription_form_requires_a_plan_or_template(client, staff_user, customer):
    client.force_login(staff_user)
    response = client.post(
        reverse("subscriptions:subscription_create"),
        {
            "customer": customer.pk,
            "start_date": "2026-06-01",
            "expiry_date": "2026-12-31",
            "payment_terms": PaymentTermFactory().pk,
        },
    )
    assert response.status_code == 200
    assert Subscription.objects.count() == 0


def test_forged_unit_price_is_ignored_when_adding_a_line(client, staff_user):
    client.force_login(staff_user)
    subscription = SubscriptionFactory()
    product = ProductFactory(sales_price=Decimal("100.00"))
    response = client.post(
        reverse("subscriptions:line_add", args=[subscription.pk]),
        {"product": product.pk, "variant": "", "quantity": "2", "unit_price": "1.00"},
    )
    assert response.status_code == 302
    line = subscription.lines.get()
    assert (line.unit_price, line.amount) == (Decimal("100.00"), Decimal("200.00"))


def test_staff_send_a_quotation_through_the_confirmation_page(client, staff_user):
    client.force_login(staff_user)
    subscription = SubscriptionFactory()
    SubscriptionLineFactory(subscription=subscription)
    url = reverse("subscriptions:subscription_action", args=[subscription.pk, "send"])
    assert client.get(url).status_code == 200
    assert client.post(url).status_code == 302
    subscription.refresh_from_db()
    assert subscription.status == Status.QUOTATION


def test_a_refused_action_shows_a_message_and_changes_nothing(client, staff_user):
    client.force_login(staff_user)
    subscription = SubscriptionFactory(status=Status.ACTIVE, plan=PlanFactory(allow_pause=False))
    url = reverse("subscriptions:subscription_action", args=[subscription.pk, "pause"])
    response = client.post(url, follow=True)
    subscription.refresh_from_db()
    assert subscription.status == Status.ACTIVE
    assert b"does not allow pausing" in response.content


# --- Customer portal --------------------------------------------------------------


def test_customer_sees_only_their_own_subscriptions(client, customer, other_customer):
    client.force_login(customer.user)
    mine = SubscriptionFactory(customer=customer, number="TEST-MINE")
    theirs = SubscriptionFactory(customer=other_customer, number="TEST-THEIRS")
    listing = client.get(reverse("portal_subscriptions:subscription_list"))
    assert b"TEST-MINE" in listing.content and b"TEST-THEIRS" not in listing.content
    mine_url = reverse("portal_subscriptions:subscription_detail", args=[mine.pk])
    theirs_url = reverse("portal_subscriptions:subscription_detail", args=[theirs.pk])
    assert client.get(mine_url).status_code == 200
    assert client.get(theirs_url).status_code == 404


def test_customer_cannot_act_on_someone_elses_subscription(client, customer, other_customer):
    client.force_login(customer.user)
    theirs = SubscriptionFactory(
        customer=other_customer, status=Status.QUOTATION, valid_until=FUTURE
    )
    url = reverse("portal_subscriptions:subscription_action", args=[theirs.pk, "accept"])
    assert client.post(url).status_code == 404
    theirs.refresh_from_db()
    assert theirs.status == Status.QUOTATION


def test_customer_accepts_a_valid_quotation(client, customer):
    client.force_login(customer.user)
    subscription = SubscriptionFactory(
        customer=customer, status=Status.QUOTATION, valid_until=FUTURE
    )
    url = reverse("portal_subscriptions:subscription_action", args=[subscription.pk, "accept"])
    assert client.post(url).status_code == 302
    subscription.refresh_from_db()
    assert subscription.status == Status.CONFIRMED


def test_expired_quotation_cannot_be_accepted_by_a_crafted_request(client, customer):
    client.force_login(customer.user)
    subscription = SubscriptionFactory(
        customer=customer, status=Status.QUOTATION, valid_until=PAST
    )
    url = reverse("portal_subscriptions:subscription_action", args=[subscription.pk, "accept"])
    response = client.post(url, follow=True)
    subscription.refresh_from_db()
    assert subscription.status == Status.QUOTATION
    assert b"has expired" in response.content


def test_customer_cannot_send_quotations_from_the_portal(client, customer):
    client.force_login(customer.user)
    subscription = SubscriptionFactory(customer=customer)
    url = reverse("portal_subscriptions:subscription_action", args=[subscription.pk, "send"])
    assert client.post(url).status_code == 404


def test_portal_actions_follow_the_plan_options(client, customer):
    client.force_login(customer.user)
    subscription = SubscriptionFactory(
        customer=customer, status=Status.ACTIVE, plan=PlanFactory(allow_pause=True)
    )
    url = reverse("portal_subscriptions:subscription_detail", args=[subscription.pk])
    response = client.get(url)
    assert b"Pause" in response.content and b"Close subscription" not in response.content


@pytest.mark.parametrize("user_fixture", ["admin_user", "staff_user"])
def test_internal_users_have_no_portal(request, client, user_fixture):
    client.force_login(request.getfixturevalue(user_fixture))
    assert client.get(reverse("portal_subscriptions:subscription_list")).status_code == 403


# --- Cron ---------------------------------------------------------------------------


def test_cron_is_closed_without_the_secret(client, settings):
    settings.CRON_SECRET = "s3cret"
    url = reverse("subscriptions:daily_cron")
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_cron_is_closed_when_no_secret_is_configured(client, settings):
    settings.CRON_SECRET = ""
    response = client.get(
        reverse("subscriptions:daily_cron"), headers={"Authorization": "Bearer "}
    )
    assert response.status_code == 403


def test_cron_runs_both_jobs_with_the_secret(client, settings):
    settings.CRON_SECRET = "s3cret"
    SubscriptionFactory(status=Status.QUOTATION, valid_until=PAST)
    response = client.get(
        reverse("subscriptions:daily_cron"), headers={"Authorization": "Bearer s3cret"}
    )
    assert response.status_code == 200
    assert len(response.json()["expired"]["done"]) == 1
