from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.accounts.models import Customer, User
from apps.catalog.models import Product
from apps.subscriptions.models import Subscription

from .exceptions import InvoiceLocked

MONEY = {"max_digits": 12, "decimal_places": 2}
ZERO = Decimal("0.00")


class InvoiceNumberSequence(models.Model):
    """Single counter row (pk=1) behind never-reused invoice numbers.

    Locked with select_for_update while a number is allocated, inside the same
    transaction as the invoice, so a rolled-back invoice gives its number back.
    """

    last_value = models.PositiveBigIntegerField(default=0)


class Invoice(models.Model):
    """The bill for one subscription and one billing period (FR-5.1, FR-5.3).

    Header and line values are copied from the subscription when the invoice is
    generated, so later catalog, plan or subscription edits never change it.
    Status changes only through services.transition_invoice.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    class EmailStatus(models.TextChoices):
        NOT_SENT = "not_sent", "Not sent"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed, retry needed"

    # Values fixed once the invoice leaves Draft (FR-5.10).
    FINANCIAL_FIELDS = (
        "number",
        "subscription_id",
        "customer_id",
        "customer_email",
        "plan_name",
        "payment_terms_name",
        "period_start",
        "period_end",
        "invoice_date",
        "due_date",
        "untaxed_amount",
        "discount_amount",
        "tax_amount",
        "total",
    )

    number = models.CharField(max_length=20, unique=True)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, related_name="invoices"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    customer_email = models.EmailField()
    plan_name = models.CharField(max_length=200)
    payment_terms_name = models.CharField(max_length=100)
    period_start = models.DateField()
    period_end = models.DateField()
    invoice_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    untaxed_amount = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY, default=ZERO)
    tax_amount = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    email_status = models.CharField(
        max_length=16, choices=EmailStatus.choices, default=EmailStatus.NOT_SENT
    )
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # BR-4 / FR-5.3: the final guard against double billing. A Cancelled
            # invoice keeps its slot, so its period is never billed again (BR-5).
            models.UniqueConstraint(
                fields=["subscription", "period_start"], name="billing_invoice_one_per_period"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "confirmed", "paid", "cancelled"]),
                name="billing_invoice_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="billing_invoice_period_ordered",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("invoice_date")),
                name="billing_invoice_due_after_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"], name="billing_invoice_status_due_idx"),
            models.Index(fields=["invoice_date"], name="billing_invoice_date_idx"),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.pk is not None:
            stored = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("status", *self.FINANCIAL_FIELDS)
                .first()
            )
            if stored and stored["status"] != self.Status.DRAFT:
                if any(stored[name] != getattr(self, name) for name in self.FINANCIAL_FIELDS):
                    raise InvoiceLocked(
                        "This invoice is no longer a draft, so its amounts can't change. "
                        "Cancel it instead."
                    )
        super().save(*args, **kwargs)

    def is_overdue_on(self, day):
        """REQUIREMENTS 7.2, applied literally: due date passed and not Paid."""
        return day > self.due_date and self.status != self.Status.PAID

    @property
    def is_overdue(self):
        return self.is_overdue_on(timezone.localdate())

    @property
    def days_overdue(self):
        return (timezone.localdate() - self.due_date).days if self.is_overdue else 0


class InvoiceLine(models.Model):
    """One product line, copied from a subscription line at generation (FR-5.1, FR-5.4).

    `tax_rate` is the product's rate when the invoice was generated. Tax is
    charged on `amount - discount_amount` (prices are tax-exclusive, BR-13).
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=300)
    is_addon = models.BooleanField(default=False)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(**MONEY)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY, default=ZERO)
    tax_amount = models.DecimalField(**MONEY)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="billing_line_quantity_gte_1"
            ),
        ]

    def _require_draft(self):
        status = Invoice.objects.filter(pk=self.invoice_id).values_list("status", flat=True).first()
        if status != Invoice.Status.DRAFT:
            raise InvoiceLocked("Lines of an issued invoice can't be changed.")

    def save(self, *args, **kwargs):
        self._require_draft()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._require_draft()
        return super().delete(*args, **kwargs)

    @property
    def total(self):
        return self.amount - self.discount_amount + self.tax_amount


class BillingRun(models.Model):
    """One bulk billing execution and its timing (FR-5.2, FR-5.9).

    A run stays Running until every due subscription has a result, so an
    interrupted run is picked up again by the next trigger (NFR-7).
    """

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"

    trigger = models.CharField(max_length=16, choices=Trigger.choices)
    triggered_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # null = the scheduler
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    run_date = models.DateField()
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "started_at"], name="billing_run_status_idx")]

    def __str__(self):
        return f"Billing run {self.pk}"


class BillingRunResult(models.Model):
    """What happened to one subscription in one run (FR-5.9)."""

    class Outcome(models.TextChoices):
        CREATED = "created", "Created"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    run = models.ForeignKey(BillingRun, on_delete=models.CASCADE, related_name="results")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, related_name="billing_results"
    )
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    invoice = models.ForeignKey(
        Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        constraints = [
            # One result per subscription per run: overlapping invocations of the
            # same run can't process a subscription twice.
            models.UniqueConstraint(
                fields=["run", "subscription"], name="billing_result_once_per_run"
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=["created", "skipped", "failed"]),
                name="billing_result_outcome_valid",
            ),
        ]
        indexes = [models.Index(fields=["run", "outcome"], name="billing_result_outcome_idx")]
