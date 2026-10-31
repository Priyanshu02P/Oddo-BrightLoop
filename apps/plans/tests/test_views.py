from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.plans.models import Plan

from .factories import PlanFactory

pytestmark = pytest.mark.django_db


def form_data(**overrides):
    data = {
        "name": "Gold",
        "price": "99.50",
        "billing_period": "monthly",
        "minimum_quantity": "2",
        "availability_start_date": "2026-01-01",
        "availability_end_date": "2026-06-30",
        "renewal_mode": "automatic",
        "auto_close_at_end_date": "on",
        "allow_pause": "on",
    }
    data.update(overrides)
    return data


def plan_urls(plan):
    return [
        reverse("plans:plan_list"),
        reverse("plans:plan_create"),
        reverse("plans:plan_detail", args=[plan.pk]),
        reverse("plans:plan_edit", args=[plan.pk]),
    ]


# --- Permissions -----------------------------------------------------------


def test_admin_can_open_every_plan_page(client, admin_user):
    client.force_login(admin_user)
    for url in plan_urls(PlanFactory()):
        assert client.get(url).status_code == 200, url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_staff_and_customer_are_denied_every_plan_page(request, client, user_fixture):
    client.force_login(request.getfixturevalue(user_fixture))
    for url in plan_urls(PlanFactory()):
        assert client.get(url).status_code == 403, url


def test_anonymous_is_sent_to_sign_in(client):
    for url in plan_urls(PlanFactory()):
        response = client.get(url)
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


@pytest.mark.parametrize("user_fixture", ["staff_user", "customer_user"])
def test_direct_writes_by_non_admins_change_nothing(request, client, user_fixture):
    plan = PlanFactory(name="Original")
    client.force_login(request.getfixturevalue(user_fixture))
    responses = [
        client.post(reverse("plans:plan_create"), form_data(name="Sneaky")),
        client.post(reverse("plans:plan_edit", args=[plan.pk]), form_data(name="Changed")),
    ]
    assert [r.status_code for r in responses] == [403, 403]
    plan.refresh_from_db()
    assert plan.name == "Original" and Plan.objects.count() == 1


def test_nav_link_is_shown_to_admin_only(client, admin_user, staff_user):
    client.force_login(admin_user)
    assert reverse("plans:plan_list") in client.get(reverse("accounts:internal_home")).text
    client.force_login(staff_user)
    assert reverse("plans:plan_list") not in client.get(reverse("accounts:internal_home")).text


# --- Create / edit ---------------------------------------------------------


def test_admin_creates_a_plan(client, admin_user):
    client.force_login(admin_user)
    response = client.post(reverse("plans:plan_create"), form_data())
    plan = Plan.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("plans:plan_detail", args=[plan.pk])
    assert plan.price == Decimal("99.50")
    assert (plan.billing_period, plan.renewal_mode, plan.minimum_quantity) == (
        "monthly",
        "automatic",
        2,
    )
    assert (plan.availability_start_date, plan.availability_end_date) == (
        date(2026, 1, 1),
        date(2026, 6, 30),
    )
    assert (
        plan.auto_close_at_end_date,
        plan.allow_close_early,
        plan.allow_pause,
        plan.allow_renew,
    ) == (
        True,
        False,
        True,
        False,
    )


def test_unchecked_lifecycle_options_are_saved_as_disabled(client, admin_user):
    plan = PlanFactory(allow_pause=True, allow_renew=True)
    client.force_login(admin_user)
    data = form_data()
    del data["allow_pause"], data["auto_close_at_end_date"]
    client.post(reverse("plans:plan_edit", args=[plan.pk]), data)
    plan.refresh_from_db()
    assert not (plan.allow_pause or plan.allow_renew or plan.auto_close_at_end_date)


def test_admin_edits_a_plan_and_values_persist(client, admin_user):
    plan = PlanFactory(name="Original")
    client.force_login(admin_user)
    response = client.post(
        reverse("plans:plan_edit", args=[plan.pk]),
        form_data(name="Renamed", billing_period="yearly", renewal_mode="manual"),
    )
    assert response.status_code == 302
    plan.refresh_from_db()
    assert (plan.name, plan.billing_period, plan.renewal_mode) == ("Renamed", "yearly", "manual")
    detail = client.get(reverse("plans:plan_detail", args=[plan.pk]))
    assert "Renamed" in detail.text and "Yearly" in detail.text


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": "   "}, "name"),
        ({"price": "abc"}, "price"),
        ({"price": "-5"}, "price"),
        ({"price": "1.005"}, "price"),
        ({"billing_period": "hourly"}, "billing_period"),
        ({"billing_period": ""}, "billing_period"),
        ({"renewal_mode": "sometimes"}, "renewal_mode"),
        ({"minimum_quantity": "0"}, "minimum_quantity"),
        ({"minimum_quantity": "1.5"}, "minimum_quantity"),
        ({"availability_start_date": ""}, "availability_start_date"),
        ({"availability_end_date": "not-a-date"}, "availability_end_date"),
        ({"availability_end_date": "2025-12-31"}, "availability_end_date"),
    ],
)
def test_invalid_input_shows_field_error_and_keeps_entered_values(
    client, admin_user, overrides, field
):
    client.force_login(admin_user)
    response = client.post(
        reverse("plans:plan_create"), form_data(**{"name": "Kept name", **overrides})
    )
    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert not Plan.objects.exists()
    if field != "name":
        assert 'value="Kept name"' in response.text


def test_forged_fields_are_ignored(client, admin_user):
    client.force_login(admin_user)
    client.post(
        reverse("plans:plan_create"),
        form_data(
            role="admin",
            is_staff="on",
            permission="manage_catalog",
            id="999",
            created_at="2000-01-01",
        ),
    )
    plan = Plan.objects.get()
    assert plan.pk != 999 and plan.created_at.year != 2000


# --- List ------------------------------------------------------------------


def test_list_shows_columns_and_status_as_text(client, admin_user):
    PlanFactory(
        name="Gold",
        price="1234.50",
        billing_period="weekly",
        minimum_quantity=4,
        availability_start_date=date(2020, 1, 1),
        availability_end_date=date(2020, 2, 1),
        renewal_mode="automatic",
        allow_pause=True,
        allow_renew=True,
    )
    client.force_login(admin_user)
    text = client.get(reverse("plans:plan_list")).text
    for expected in (
        "Gold",
        "1,234.50",
        "Weekly",
        "2020-01-01 to 2020-02-01",
        "Automatic",
        "Pause, Renew",
        "Ended",
    ):
        assert expected in text


def test_list_empty_state_and_pagination(client, admin_user, django_assert_max_num_queries):
    client.force_login(admin_user)
    assert "No plans exist yet" in client.get(reverse("plans:plan_list")).text
    for _ in range(30):
        PlanFactory()
    with django_assert_max_num_queries(6):
        response = client.get(reverse("plans:plan_list"))
    assert len(response.context["page"]) == 25
    assert len(client.get(reverse("plans:plan_list") + "?page=2").context["page"]) == 5
