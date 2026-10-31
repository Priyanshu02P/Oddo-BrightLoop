from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

MONEY = {"max_digits": 12, "decimal_places": 2}
NON_NEGATIVE = [MinValueValidator(Decimal("0.00"))]


class Tax(models.Model):
    """Named tax rate (FR-9.1). Administered by M9; the catalog only references it."""

    name = models.CharField(max_length=100)
    rate = models.DecimalField(
        max_digits=5, decimal_places=2, validators=NON_NEGATIVE, help_text="Percentage."
    )

    class Meta:
        verbose_name_plural = "taxes"
        constraints = [
            models.CheckConstraint(condition=models.Q(rate__gte=0), name="catalog_tax_rate_gte_0"),
        ]

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class PaymentTerm(models.Model):
    """Due-date rule such as Net 30 (FR-9.3). Administered by M9; M4 only references it."""

    name = models.CharField(max_length=100)
    days = models.PositiveIntegerField(help_text="Days from the invoice date until it is due.")

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available_for_new_lines(self):
        """Products that may be put on a new subscription line (FR-2.4)."""
        return self.filter(is_archived=False)


class Product(models.Model):
    """Sellable item (FR-2.1). Prices are tax-exclusive (BR-13); archived instead of deleted."""

    class Type(models.TextChoices):
        SERVICE = "service", "Service"
        GOODS = "goods", "Goods"

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=16, choices=Type.choices)
    sales_price = models.DecimalField(**MONEY, validators=NON_NEGATIVE)
    cost_price = models.DecimalField(**MONEY, validators=NON_NEGATIVE)
    notes = models.TextField(blank=True)
    tax = models.ForeignKey(Tax, on_delete=models.PROTECT, related_name="products")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(name=""), name="catalog_product_name_set"),
            models.CheckConstraint(
                condition=models.Q(type__in=["service", "goods"]),
                name="catalog_product_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(sales_price__gte=0), name="catalog_product_sales_price_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0), name="catalog_product_cost_price_gte_0"
            ),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    """One variant value (e.g. Brand: Odoo) and its additive price adjustment (FR-2.2)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    dimension = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(**MONEY, validators=NON_NEGATIVE)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(dimension="") & ~models.Q(value=""),
                name="catalog_variant_dimension_value_set",
            ),
            models.CheckConstraint(
                condition=models.Q(price_adjustment__gte=0),
                name="catalog_variant_price_adjustment_gte_0",
            ),
        ]

    def __str__(self):
        return f"{self.dimension}: {self.value}"

    @property
    def adjusted_sales_price(self):
        """Base sales price plus this value's adjustment, before tax. Cost price is unaffected."""
        return self.product.sales_price + self.price_adjustment
