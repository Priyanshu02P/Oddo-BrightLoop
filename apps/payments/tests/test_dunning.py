import time
from datetime import timedelta

import pytest

from apps.billing.models import Invoice
from apps.billing.tests.factories import InvoiceFactory
from apps.payments import dunning, notifications
from apps.payments.models import DunningReminder

from .factories import TODAY, confirmed_invoice

pytestmark = pytest.mark.django_db


def due(days_ago, **overrides):
    return confirmed_invoice(
        due_date=TODAY - timedelta(days=days_ago),
        invoice_date=TODAY - timedelta(days=60),
        **overrides,
    )


@pytest.mark.parametrize(
    "days, stage", [(-3, None), (0, None), (1, 1), (6, 1), (7, 2), (13, 2), (14, 3), (90, 3)]
)
def test_stage_follows_the_cadence(days, stage):
    assert dunning.stage_for(days) == stage


def test_each_overdue_invoice_gets_its_current_stage(sent_reminders):
    due_today, one, seven, fourteen = due(0), due(1), due(7), due(20)
    result = dunning.run_dunning(TODAY)
    assert sorted(sent_reminders, key=lambda s: s[1]) == [
        (one.number, 1, 1),
        (seven.number, 2, 7),
        (fourteen.number, 3, 20),  # earlier stages are not sent late
    ]
    assert (result["sent"], result["complete"]) == (3, True)
    assert not due_today.dunning_reminders.exists()  # due today is not overdue
    reminder = DunningReminder.objects.get(invoice=one)
    assert (reminder.status, reminder.attempts, reminder.days_past_due) == ("sent", 1, 1)
    assert reminder.sent_at is not None


def test_a_rerun_sends_nothing_twice(sent_reminders):
    due(1)
    dunning.run_dunning(TODAY)
    assert dunning.run_dunning(TODAY)["sent"] == 0
    assert len(sent_reminders) == 1


def test_the_next_stage_follows_when_its_day_comes(sent_reminders):
    invoice = due(1)
    dunning.run_dunning(TODAY)
    dunning.run_dunning(TODAY + timedelta(days=6))
    assert [s[1] for s in sent_reminders] == [1, 2]
    assert list(invoice.dunning_reminders.values_list("stage", flat=True)) == [1, 2]


@pytest.mark.parametrize(
    "status", [Invoice.Status.PAID, Invoice.Status.CANCELLED, Invoice.Status.DRAFT]
)
def test_unpayable_invoices_get_no_reminders(sent_reminders, status):
    InvoiceFactory(
        status=status, due_date=TODAY - timedelta(days=10), invoice_date=TODAY - timedelta(days=40)
    )
    dunning.run_dunning(TODAY)
    assert sent_reminders == []


def test_an_invoice_paid_after_selection_is_skipped(sent_reminders):
    invoice = due(3)
    Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.PAID)
    assert dunning.send_reminder(invoice.pk, 1, TODAY) == "skipped"
    assert sent_reminders == []


def test_a_failed_email_does_not_stop_the_others_and_is_retried(
    monkeypatch, sent_reminders, caplog
):
    broken, fine = due(2), due(3)
    real = notifications.send_overdue_reminder

    def flaky(invoice, **kwargs):
        if invoice.pk == broken.pk:
            raise ConnectionRefusedError("smtp down")
        return real(invoice, **kwargs)

    monkeypatch.setattr(notifications, "send_overdue_reminder", flaky)
    result = dunning.run_dunning(TODAY)
    assert (result["sent"], result["failed"]) == (1, 1)
    assert [s[0] for s in sent_reminders] == [fine.number]
    failed = DunningReminder.objects.get(invoice=broken)
    assert (failed.status, failed.attempts) == ("failed", 1)  # tried once per run
    assert "smtp down" not in failed.failure_reason and "smtp down" in caplog.text

    monkeypatch.setattr(notifications, "send_overdue_reminder", real)
    assert dunning.run_dunning(TODAY)["sent"] == 1
    failed.refresh_from_db()
    assert (failed.status, failed.attempts) == ("sent", 2)


def test_retries_stop_at_the_attempt_limit(monkeypatch, settings):
    settings.DUNNING_MAX_ATTEMPTS = 2
    invoice = due(2)

    def refuse(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr(notifications, "send_overdue_reminder", refuse)
    for _ in range(4):
        dunning.run_dunning(TODAY)
    assert DunningReminder.objects.get(invoice=invoice).attempts == 2


def test_a_run_out_of_time_resumes_later(sent_reminders):
    due(2)
    assert dunning.run_dunning(TODAY, deadline=time.monotonic() - 1)["complete"] is False
    assert sent_reminders == []
    assert dunning.run_dunning(TODAY)["sent"] == 1


def test_the_subscription_is_not_paused_after_the_final_reminder():
    invoice = due(30)
    dunning.run_dunning(TODAY)
    invoice.subscription.refresh_from_db()
    assert invoice.subscription.status != "paused"  # deferred until Open Item C is confirmed
