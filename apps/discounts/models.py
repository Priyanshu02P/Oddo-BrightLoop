"""Discount models: Discount, DiscountProduct, DiscountRedemption, InvoiceDiscountSnapshot.

M6 owns discount rules, redemptions, and the stacking engine.
M5 (billing) owns invoices; InvoiceDiscountSnapshot links back to billing.Invoice.
"""

from django.db import models
from django.utils import timezone

from apps.accounts.models import Customer, User
from apps.catalog.models import Product

MONEY = {"max_digits": 12, "decimal_places": 2}


class Discount(models.Model):
    """Admin-configured discount rule (FR-6.1 through FR-6.4)."""

    class DiscountType(models.TextChoices):
        FIXED_AMOUNT = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    class ScopeType(models.TextChoices):
        SELECTED_PRODUCTS = "selected_products", "Selected products"
        WHOLE_SUBSCRIPTION = "whole_subscription", "Whole subscription"

    name = models.CharField(max_length=200)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    value = models.DecimalField(**MONEY)
    minimum_purchase_amount = models.DecimalField(**MONEY, null=True, blank=True)
    minimum_quantity = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    usage_limit_per_customer = models.PositiveIntegerField()
    scope_type = models.CharField(max_length=32, choices=ScopeType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["is_active", "start_date", "end_date"], name="discount_active_dates_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__gt=0),
                name="discount_value_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(usage_limit_per_customer__gte=1),
                name="discount_usage_limit_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="discount_end_gte_start",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_type__in=["fixed", "percentage"]),
                name="discount_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(scope_type__in=["selected_products", "whole_subscription"]),
                name="discount_scope_type_valid",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_expired_on(self):
        from django.utils import timezone as tz

        return tz.localdate() > self.end_date

    def status_label(self, as_of=None):
        """Derived status label for display. Not stored."""
        from django.utils import timezone as tz

        today = as_of or tz.localdate()
        if not self.is_active:
            return "inactive"
        if today < self.start_date:
            return "upcoming"
        if today > self.end_date:
            return "expired"
        return "active"


class DiscountProduct(models.Model):
    """M2M through table: discount → product for SELECTED_PRODUCTS scope (FR-6.4)."""

    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="discount_products"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["discount", "product"], name="discount_product_unique"),
        ]

    def __str__(self):
        return f"{self.discount} / {self.product}"


class DiscountRedemption(models.Model):
    """Per-customer usage counter (FR-6.8, BR-10). Created on first confirmation."""

    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name="redemptions")
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="discount_redemptions"
    )
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["discount", "customer"], name="discount_redemption_lookup_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["discount", "customer"], name="discount_redemption_unique"
            ),
        ]

    def __str__(self):
        return f"{self.discount} / {self.customer} ({self.usage_count} uses)"


class InvoiceDiscountSnapshot(models.Model):
    """Immutable record of a discount applied to an invoice (FR-6.5, FR-5.10).

    Snapshot fields preserve the rule values at calculation time so that later
    edits to the Discount rule do not change historical invoice calculations.
    """

    invoice = models.ForeignKey(
        "billing.Invoice", on_delete=models.CASCADE, related_name="discount_snapshots"
    )
    discount = models.ForeignKey(
        Discount, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Snapshot fields — frozen at invoice generation time.
    discount_name = models.CharField(max_length=200)
    discount_type = models.CharField(max_length=16)
    discount_value = models.DecimalField(**MONEY)
    scope_type = models.CharField(max_length=32)
    application_order = models.PositiveSmallIntegerField()
    amount_applied = models.DecimalField(**MONEY)
    redemption_confirmed = models.BooleanField(default=False)

    class Meta:
        ordering = ["application_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "discount"], name="discount_snapshot_unique_per_invoice"
            ),
        ]

    def __str__(self):
        return f"{self.discount_name} on invoice {self.invoice_id}"
