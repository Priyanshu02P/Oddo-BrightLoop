from datetime import date
from decimal import Decimal

import factory

from apps.plans.models import Plan


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Plan

    name = factory.Sequence(lambda n: f"Plan {n}")
    price = Decimal("1500.00")
    billing_period = Plan.BillingPeriod.MONTHLY
    minimum_quantity = 1
    availability_start_date = date(2026, 1, 1)
    availability_end_date = date(2026, 12, 31)
    renewal_mode = Plan.RenewalMode.MANUAL
