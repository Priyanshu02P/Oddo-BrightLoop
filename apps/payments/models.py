from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import MONEY, Invoice


class PaymentReferenceSequence(models.Model):
    """Single counter row (pk=1) behind never-reused payment references."""

    last_value = models.PositiveBigIntegerField(default=0)


class Payment(models.Model):
    """One attempt to settle one invoice (FR-7.1 to FR-7.4).

    Failed and pending attempts are kept for traceability; only a Succeeded
    payment settles the invoice, and an invoice has at most one payment that is
    Pending or Succeeded at a time (enforced by the database).
    """

    class Method(models.TextChoices):
        # Recorded by staff once the money has arrived (M7 open decision 1).
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CARD = "card", "Card"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        # Collected through the mock PaymentProvider; development and tests only.
        TEST_GATEWAY = "test_gateway", "Test gateway (simulated)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    reference = models.CharField(max_length=20, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=24, choices=Method.choices)
    amount = models.DecimalField(**MONEY)
    payment_date = models.DateField()
    note = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    provider_reference = models.CharField(max_length=64, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # FR-7.9 / §5.6: at most one payment that settles, or may still
            # settle, an invoice. Concurrent requests can't both pass.
            models.UniqueConstraint(
                fields=["invoice"],
                condition=models.Q(status__in=["pending", "succeeded"]),
                name="payments_one_open_or_paid_per_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "succeeded", "failed"]),
                name="payments_payment_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payments_payment_amount_gt_0"
            ),
        ]
        indexes = [
            models.Index(fields=["payment_date"], name="payments_date_idx"),
            models.Index(fields=["status", "method"], name="payments_status_method_idx"),
        ]

    def __str__(self):
        return self.reference

    @property
    def is_simulated(self):
        return self.method == self.Method.TEST_GATEWAY


class DunningReminder(models.Model):
    """One overdue reminder stage for one invoice (FR-7.8, §8.2).

    A stage is sent at most once; a failed send is retried by later runs until
    it succeeds or reaches the attempt limit.
    """

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="dunning_reminders")
    stage = models.PositiveSmallIntegerField()
    days_past_due = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["stage"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "stage"], name="payments_reminder_once"),
            models.CheckConstraint(
                condition=models.Q(status__in=["sent", "failed"]),
                name="payments_reminder_status_valid",
            ),
        ]
