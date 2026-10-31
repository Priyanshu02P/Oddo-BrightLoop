from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PlanQuerySet(models.QuerySet):
    def available_on(self, start_date):
        """Plans selectable for a new subscription starting on `start_date` (FR-3.5).

        Both boundary dates are inclusive (assumption for M3-O2).
        """
        return self.filter(
            availability_start_date__lte=start_date, availability_end_date__gte=start_date
        )

    def pending_auto_close(self, today):
        """Auto-close plans whose end date has passed (FR-3.6)."""
        return self.filter(auto_close_at_end_date=True, availability_end_date__lt=today)


class Plan(models.Model):
    """Commercial and lifecycle configuration a subscription follows (FR-3.1 to FR-3.4).

    Prices are tax-exclusive (BR-13). Plans are never deleted or archived in M3
    (open decision M3-O10), and editing one does not touch subscriptions.
    """

    class BillingPeriod(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    class RenewalMode(models.TextChoices):
        AUTOMATIC = "automatic", "Automatic"
        MANUAL = "manual", "Manual"

    class Availability(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        AVAILABLE = "available", "Available"
        ENDED = "ended", "Ended"

    name = models.CharField(max_length=200)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    billing_period = models.CharField(max_length=16, choices=BillingPeriod.choices)
    minimum_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    availability_start_date = models.DateField()
    availability_end_date = models.DateField()
    renewal_mode = models.CharField(max_length=16, choices=RenewalMode.choices)
    auto_close_at_end_date = models.BooleanField(default=False)
    allow_close_early = models.BooleanField(default=False)
    allow_pause = models.BooleanField(default=False)
    allow_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(name=""), name="plans_plan_name_set"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="plans_plan_price_gte_0"),
            models.CheckConstraint(
                condition=models.Q(billing_period__in=["daily", "weekly", "monthly", "yearly"]),
                name="plans_plan_billing_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(renewal_mode__in=["automatic", "manual"]),
                name="plans_plan_renewal_mode_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_quantity__gte=1),
                name="plans_plan_minimum_quantity_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(availability_end_date__gte=models.F("availability_start_date")),
                name="plans_plan_availability_window_ordered",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if not (self.name or "").strip():
            raise ValidationError({"name": "The plan name can't be blank."})
        start, end = self.availability_start_date, self.availability_end_date
        if start and end and end < start:
            raise ValidationError(
                {"availability_end_date": "The end date can't be earlier than the start date."}
            )

    def is_available_on(self, start_date):
        """Inclusive window check for a proposed new-subscription start date (FR-3.5)."""
        return self.availability_start_date <= start_date <= self.availability_end_date

    def availability_on(self, today):
        if today < self.availability_start_date:
            return self.Availability.UPCOMING
        if today > self.availability_end_date:
            return self.Availability.ENDED
        return self.Availability.AVAILABLE

    @property
    def availability(self):
        """Today's availability for new subscriptions (display status; not stored)."""
        return self.availability_on(timezone.localdate())

    @property
    def availability_label(self):
        return self.Availability(self.availability).label

    @property
    def enabled_lifecycle_options(self):
        """Labels of the enabled lifecycle options, for display."""
        options = (
            (self.auto_close_at_end_date, "Auto-close at end date"),
            (self.allow_close_early, "Close early"),
            (self.allow_pause, "Pause"),
            (self.allow_renew, "Renew"),
        )
        return [label for enabled, label in options if enabled]
