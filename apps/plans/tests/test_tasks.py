import logging
from datetime import date

import pytest
from django.urls import reverse

from apps.plans import tasks

from .factories import PlanFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 1)


class Recorder:
    def __init__(self, fail_on=()):
        self.plans = []
        self.fail_on = fail_on

    def __call__(self, plan):
        if plan.pk in self.fail_on:
            raise RuntimeError("boom")
        self.plans.append(plan.pk)


def test_only_expired_auto_close_plans_are_handed_to_the_hook():
    due = PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 6, 30))
    PlanFactory(auto_close_at_end_date=False, availability_end_date=date(2026, 6, 30))
    PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 7, 1))
    hook = Recorder()
    result = tasks.run_auto_close(hook, today=TODAY)
    assert hook.plans == [due.pk]
    assert result == {"processed_plan_ids": [due.pk], "failed_plan_ids": []}


def test_nothing_to_do_when_no_plan_is_due():
    PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 7, 1))
    hook = Recorder()
    assert tasks.run_auto_close(hook, today=TODAY)["processed_plan_ids"] == []
    assert hook.plans == []


def test_a_failing_plan_is_logged_and_the_others_still_run(caplog):
    first = PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 6, 1))
    second = PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 6, 2))
    hook = Recorder(fail_on={first.pk})
    with caplog.at_level(logging.ERROR, logger="apps.plans.tasks"):
        result = tasks.run_auto_close(hook, today=TODAY)
    assert result == {"processed_plan_ids": [second.pk], "failed_plan_ids": [first.pk]}
    assert f"Auto-close failed for plan {first.pk}" in caplog.text


def test_rerunning_selects_the_same_plans_so_the_hook_must_be_idempotent():
    due = PlanFactory(auto_close_at_end_date=True, availability_end_date=date(2026, 6, 30))
    hook = Recorder()
    tasks.run_auto_close(hook, today=TODAY)
    tasks.run_auto_close(hook, today=TODAY)
    assert hook.plans == [due.pk, due.pk]


# --- Cron endpoint ----------------------------------------------------------

CALLS = []


def recording_handler(plan):
    CALLS.append(plan.pk)


@pytest.fixture
def cron_url():
    return reverse("plans:auto_close_cron")


@pytest.fixture
def cron_settings(settings):
    settings.CRON_SECRET = "s3cret"
    settings.PLANS_AUTO_CLOSE_HANDLER = f"{__name__}.recording_handler"
    CALLS.clear()


def test_cron_rejects_missing_or_wrong_secret(client, cron_url, cron_settings):
    PlanFactory(
        auto_close_at_end_date=True,
        availability_start_date=date(2019, 1, 1),
        availability_end_date=date(2020, 1, 1),
    )
    assert client.get(cron_url).status_code == 403
    assert client.get(cron_url, headers={"Authorization": "Bearer nope"}).status_code == 403
    assert CALLS == []


def test_cron_is_closed_when_no_secret_is_configured(client, cron_url, settings):
    settings.CRON_SECRET = ""
    assert client.get(cron_url, headers={"Authorization": "Bearer "}).status_code == 403
    assert client.get(cron_url).status_code == 403


def test_cron_rejects_a_logged_in_admin_without_the_secret(
    client, cron_url, cron_settings, admin_user
):
    client.force_login(admin_user)
    assert client.get(cron_url).status_code == 403


def test_cron_runs_the_task_with_the_secret(client, cron_url, cron_settings):
    plan = PlanFactory(
        auto_close_at_end_date=True,
        availability_start_date=date(2019, 1, 1),
        availability_end_date=date(2020, 1, 1),
    )
    response = client.get(cron_url, headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 200
    assert response.json() == {"processed_plan_ids": [plan.pk], "failed_plan_ids": []}
    assert CALLS == [plan.pk]


def test_cron_reports_when_the_handler_is_not_configured(client, cron_url, settings):
    settings.CRON_SECRET = "s3cret"
    settings.PLANS_AUTO_CLOSE_HANDLER = ""
    response = client.get(cron_url, headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 503


def test_cron_only_accepts_get(client, cron_url, cron_settings):
    assert client.post(cron_url, headers={"Authorization": "Bearer s3cret"}).status_code == 405
