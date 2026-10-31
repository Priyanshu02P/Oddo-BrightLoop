import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.permissions import Permission, has_permission

from .exceptions import PlanNotAvailable
from .models import Plan

logger = logging.getLogger(__name__)

PLAN_FIELDS = (
    "name",
    "price",
    "billing_period",
    "minimum_quantity",
    "availability_start_date",
    "availability_end_date",
    "renewal_mode",
    "auto_close_at_end_date",
    "allow_close_early",
    "allow_pause",
    "allow_renew",
)


def _require_plan_admin(actor):
    # Checked here as well as in the views, so the services are safe from any entry point.
    if not has_permission(actor, Permission.MANAGE_CATALOG):
        raise PermissionDenied


def _apply(plan, data):
    for name in PLAN_FIELDS:
        setattr(plan, name, data[name])
    plan.full_clean()
    plan.save()


def create_plan(*, actor, fields):
    """Create a plan (FR-3.1 to FR-3.4)."""
    _require_plan_admin(actor)
    with transaction.atomic():
        plan = Plan()
        _apply(plan, fields)
    logger.info("Plan %s created by user %s", plan.pk, actor.pk)
    return plan


def update_plan(*, actor, plan, fields):
    """Update a plan's configuration.

    Only the plan record changes; subscriptions, invoices and their stored
    prices are not rewritten (M3-O11).
    """
    _require_plan_admin(actor)
    with transaction.atomic():
        plan = Plan.objects.select_for_update().get(pk=plan.pk)
        _apply(plan, fields)
    logger.info("Plan %s updated by user %s", plan.pk, actor.pk)
    return plan


def require_plan_available(plan, start_date):
    """Server-side gate for new subscriptions (FR-3.5); M4 calls this on create.

    Existing subscriptions are never checked against this window.
    """
    if not plan.is_available_on(start_date):
        raise PlanNotAvailable(
            f"Plan “{plan.name}” is only available for new subscriptions from "
            f"{plan.availability_start_date:%Y-%m-%d} to {plan.availability_end_date:%Y-%m-%d}."
        )
