from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import Customer
from apps.catalog.models import PaymentTerm, Product, ProductVariant
from apps.plans.models import Plan

MONEY = {"max_digits": 12, "decimal_places": 2}
ZERO = Decimal("0.00")


class QuotationTemplate(models.Model):
    """Reusable plan and product lines plus a validity period in days (FR-4.1).

    Lines carry no price: every subscription line is priced from the catalog
    when it is created (open decision: template line schema).
    """

    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="quotation_templates")
    validity_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(name=""), name="subs_template_name_set"),
            models.CheckConstraint(
                condition=models.Q(validity_days__gte=1), name="subs_template_validity_gte_1"
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if not (self.name or "").strip():
            raise ValidationError({"name": "The template name can't be blank."})


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_addon = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="subs_template_line_quantity_gte_1"
            ),
        ]

    def clean(self):
        if self.variant_id and self.product_id and self.variant.product_id != self.product_id:
            raise ValidationError({"variant": "This variant does not belong to the product."})


class SubscriptionNumberSequence(models.Model):
    """Single counter row (pk=1) behind never-reused subscription numbers (FR-4.15).

    The row is locked with select_for_update while a number is allocated, so
    parallel serverless invocations are serialized by PostgreSQL.
    """

    last_value = models.PositiveBigIntegerField(default=0)


class Subscription(models.Model):
    """A customer's contract with one plan (FR-4.3, BR-3). Status changes only
    through services.transition_subscription."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTATION = "quotation", "Quotation"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    class ClosedReason(models.TextChoices):
        EXPIRED = "expired", "Quotation expired"
        CANCELLED = "cancelled", "Cancelled"
        PLAN_ENDED = "plan_ended", "Plan ended"

    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    payment_terms = models.ForeignKey(PaymentTerm, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    closed_reason = models.CharField(max_length=16, choices=ClosedReason.choices, blank=True)
    start_date = models.DateField()
    expiry_date = models.DateField()
    quotation_validity_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    valid_until = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    payment_failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status"], name="subs_subscription_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["draft", "quotation", "confirmed", "active", "paused", "closed"]
                ),
                name="subs_subscription_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(expiry_date__gte=models.F("start_date")),
                name="subs_subscription_dates_ordered",
            ),
            models.CheckConstraint(
                condition=models.Q(quotation_validity_days__gte=1),
                name="subs_subscription_validity_gte_1",
            ),
        ]

    def __str__(self):
        return self.number

    @property
    def untaxed_total(self):
        return sum((line.amount for line in self.lines.all()), ZERO)

    @property
    def tax_total(self):
        return sum((line.tax_amount for line in self.lines.all()), ZERO)

    @property
    def total(self):
        return self.untaxed_total + self.tax_total

    def is_quotation_valid_on(self, day):
        """Acceptance is open through `valid_until` itself (assumption)."""
        return self.valid_until is not None and day <= self.valid_until


class SubscriptionLine(models.Model):
    """Product line (or add-on, FR-4.12) with prices stored when it was created,
    so later catalog edits never rewrite an existing subscription (FR-4.2, FR-4.4)."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(**MONEY)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(**MONEY)
    tax_amount = models.DecimalField(**MONEY)
    is_addon = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="subs_line_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="subs_line_unit_price_gte_0"
            ),
        ]
