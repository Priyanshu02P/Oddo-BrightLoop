"""Subscription writes: creation, lines, lifecycle (FR-4.2 to FR-4.5, FR-4.10, FR-4.11, FR-4.15)."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission
from apps.plans.services import require_plan_available

from . import notifications, pricing
from .exceptions import (
    ActionNotAllowedByPlan,
    EmptyQuotation,
    InvalidSubscriptionTransition,
    QuotationExpired,
    QuotationNotExpired,
    SubscriptionNotEditable,
)
from .models import Subscription, SubscriptionLine, SubscriptionNumberSequence

logger = logging.getLogger(__name__)

Status = Subscription.Status

# The only place that says which status changes are legal (REQUIREMENTS 7.1).
ALLOWED_TRANSITIONS = {
    Status.DRAFT: {Status.QUOTATION},
    Status.QUOTATION: {Status.CONFIRMED, Status.CLOSED},
    Status.CONFIRMED: {Status.ACTIVE},
    Status.ACTIVE: {Status.PAUSED, Status.CLOSED},
    Status.PAUSED: {Status.ACTIVE, Status.CLOSED},
    Status.CLOSED: set(),
}


# --- Authorization -----------------------------------------------------------


def _require_internal(actor, permission=Permission.MANAGE_SUBSCRIPTIONS):
    if not has_permission(actor, permission):
        raise PermissionDenied


def _require_access(actor, subscription, *, internal, own):
    """Internal roles by permission; a Customer only on their own record (FR-1.7)."""
    if has_permission(actor, internal):
        return
    if has_permission(actor, own) and subscription.customer.user_id == actor.pk:
        return
    raise PermissionDenied


# --- The single status door --------------------------------------------------


def transition_subscription(
    subscription, to_status, *, actor=None, closed_reason="", changes=None, validate=None
):
    """Move a subscription to `to_status`; the only code that assigns status.

    Locks the row, checks the transition table, runs `validate(locked)` (extra
    checks that must see the locked row), applies `changes`, saves and writes
    the audit entry in one transaction. `actor=None` is the system.
    """
    with transaction.atomic():
        locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
        if to_status not in ALLOWED_TRANSITIONS[locked.status]:
            raise InvalidSubscriptionTransition(
                f"A {locked.get_status_display().lower()} subscription can't "
                f"move to {Status(to_status).label.lower()}."
            )
        if validate is not None:
            validate(locked)
        from_status = locked.status
        locked.status = to_status
        locked.closed_reason = closed_reason
        for name, value in (changes or {}).items():
            setattr(locked, name, value)
        locked.save()
        record_audit(
            actor=actor,
            action="subscription.status_changed",
            target=locked,
            from_status=from_status,
            to_status=to_status,
        )
    logger.info("Subscription %s: %s -> %s", locked.pk, from_status, to_status)
    return locked


# --- Creation and lines ------------------------------------------------------


def _allocate_number():
    """Next sequential number (FR-4.15). Must run inside a transaction: the
    counter row stays locked until it commits."""
    SubscriptionNumberSequence.objects.get_or_create(pk=1)
    sequence = SubscriptionNumberSequence.objects.select_for_update().get(pk=1)
    sequence.last_value += 1
    sequence.save(update_fields=["last_value"])
    return f"SUB-{sequence.last_value:06d}"


def _create_line(subscription, row):
    values = pricing.price_line(
        product=row["product"], variant=row.get("variant"), quantity=row["quantity"]
    )
    line = SubscriptionLine(
        subscription=subscription,
        product=row["product"],
        variant=row.get("variant"),
        quantity=row["quantity"],
        is_addon=row.get("is_addon", False),
        **values,
    )
    line.full_clean()
    line.save()
    return line


def _template_rows(template):
    return [
        {
            "product": line.product,
            "variant": line.variant,
            "quantity": line.quantity,
            "is_addon": line.is_addon,
        }
        for line in template.lines.select_related("product__tax", "variant")
    ]


def create_subscription(
    *, actor, customer, plan, payment_terms, start_date, expiry_date, template=None, lines=()
):
    """Create a Draft subscription, optionally by copying a template (FR-4.1 to FR-4.4).

    With a template, its plan and lines are copied into subscription-owned
    lines and any `plan`/`lines` argument is ignored. Prices come from the
    catalog, never from the caller.
    """
    _require_internal(actor)
    if template is not None:
        _require_internal(actor, Permission.USE_QUOTATION_TEMPLATES)
        plan = template.plan
        lines = _template_rows(template)
        validity_days = template.validity_days
    else:
        validity_days = settings.QUOTATION_DEFAULT_VALIDITY_DAYS
    require_plan_available(plan, start_date)
    with transaction.atomic():
        subscription = Subscription(
            number=_allocate_number(),
            customer=customer,
            plan=plan,
            payment_terms=payment_terms,
            start_date=start_date,
            expiry_date=expiry_date,
            quotation_validity_days=validity_days,
        )
        subscription.full_clean()
        subscription.save()
        for row in lines:
            _create_line(subscription, row)
        record_audit(actor=actor, action="subscription.created", target=subscription)
    logger.info("Subscription %s created by user %s", subscription.pk, actor.pk)
    return subscription


def _locked_draft(subscription):
    locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
    if locked.status != Status.DRAFT:
        raise SubscriptionNotEditable(
            "Lines can only be changed while the subscription is a Draft."
        )
    return locked


def add_line(*, actor, subscription, row):
    _require_internal(actor)
    with transaction.atomic():
        locked = _locked_draft(subscription)
        line = _create_line(locked, row)
        record_audit(actor=actor, action="subscription.line_added", target=locked)
    return line


def update_line(*, actor, line, row):
    _require_internal(actor)
    with transaction.atomic():
        locked = _locked_draft(line.subscription)
        line = SubscriptionLine.objects.select_for_update().get(pk=line.pk, subscription=locked)
        values = pricing.price_line(
            product=row["product"], variant=row.get("variant"), quantity=row["quantity"]
        )
        line.product = row["product"]
        line.variant = row.get("variant")
        line.quantity = row["quantity"]
        line.is_addon = row.get("is_addon", False)
        for name, value in values.items():
            setattr(line, name, value)
        line.full_clean()
        line.save()
        record_audit(actor=actor, action="subscription.line_updated", target=locked)
    return line


def remove_line(*, actor, line):
    _require_internal(actor)
    with transaction.atomic():
        locked = _locked_draft(line.subscription)
        SubscriptionLine.objects.filter(pk=line.pk, subscription=locked).delete()
        record_audit(actor=actor, action="subscription.line_removed", target=locked)


# --- Quotation lifecycle -----------------------------------------------------


def _notify_quotation_sent(subscription):
    # Email failure must never undo the committed business change (FR-10.4).
    # There is no notification log until M10, so the failure is logged for retry.
    try:
        notifications.send_quotation_email(subscription)
    except OSError:
        logger.exception("Quotation email for subscription %s failed", subscription.pk)


def send_quotation(*, actor, subscription):
    """Draft -> Quotation: fix the validity deadline and email the customer (FR-4.5)."""
    _require_internal(actor)

    def validate(locked):
        if not locked.lines.exists():
            raise EmptyQuotation("Add at least one line before sending the quotation.")

    valid_until = timezone.localdate() + timedelta(days=subscription.quotation_validity_days)
    sent = transition_subscription(
        subscription,
        Status.QUOTATION,
        actor=actor,
        changes={"valid_until": valid_until},
        validate=validate,
    )
    _notify_quotation_sent(sent)
    return sent


def accept_quotation(*, actor, subscription):
    """Quotation -> Confirmed; ownership, status and expiry are rechecked here (FR-4.11)."""
    _require_access(
        actor,
        subscription,
        internal=Permission.ACCEPT_QUOTATION,
        own=Permission.ACCEPT_OWN_QUOTATION,
    )
    today = timezone.localdate()

    def validate(locked):
        if not locked.is_quotation_valid_on(today):
            raise QuotationExpired("This quotation has expired and can no longer be accepted.")

    return transition_subscription(subscription, Status.CONFIRMED, actor=actor, validate=validate)


# --- Plan-governed lifecycle actions ------------------------------------------


def _require_plan_option(option, label):
    def validate(locked):
        if not getattr(locked.plan, option):
            raise ActionNotAllowedByPlan(f"The plan “{locked.plan.name}” does not allow {label}.")

    return validate


def _require_manage(actor, subscription):
    _require_access(
        actor,
        subscription,
        internal=Permission.MANAGE_SUBSCRIPTIONS,
        own=Permission.MANAGE_OWN_SUBSCRIPTIONS,
    )


def pause_subscription(*, actor, subscription):
    """Active -> Paused when the plan allows it; paused subscriptions are not billed (BR-6)."""
    _require_manage(actor, subscription)
    return transition_subscription(
        subscription,
        Status.PAUSED,
        actor=actor,
        validate=_require_plan_option("allow_pause", "pausing"),
    )


def resume_subscription(*, actor, subscription):
    """Paused -> Active and recalculate the next billing date (FR-4.10).

    Provisional rule (open decision): billing resumes from the resume date, or
    from the stored date if that is still in the future.
    """
    _require_manage(actor, subscription)
    today = timezone.localdate()
    next_date = max(subscription.next_billing_date or today, today)
    return transition_subscription(
        subscription, Status.ACTIVE, actor=actor, changes={"next_billing_date": next_date}
    )


def cancel_subscription(*, actor, subscription):
    """Active/Paused -> Closed when the plan allows closing early."""
    _require_manage(actor, subscription)
    return transition_subscription(
        subscription,
        Status.CLOSED,
        actor=actor,
        closed_reason=Subscription.ClosedReason.CANCELLED,
        validate=_require_plan_option("allow_close_early", "closing a subscription early"),
    )


# --- System transitions (called by scheduled jobs; actor is the system) ------


def expire_quotation(subscription, today):
    def validate(locked):
        if locked.is_quotation_valid_on(today):
            raise QuotationNotExpired("Still valid.")

    return transition_subscription(
        subscription,
        Status.CLOSED,
        closed_reason=Subscription.ClosedReason.EXPIRED,
        validate=validate,
    )


def activate_subscription(subscription, today):
    """Confirmed -> Active once the start date is reached (FR-4.14, working assumption H).

    The first billing date is the start date (provisional; M5 owns billing rules).
    """

    def validate(locked):
        if locked.start_date > today:
            raise InvalidSubscriptionTransition("The start date has not been reached.")

    return transition_subscription(
        subscription,
        Status.ACTIVE,
        changes={"next_billing_date": subscription.start_date},
        validate=validate,
    )


def close_for_plan_end(subscription):
    return transition_subscription(
        subscription, Status.CLOSED, closed_reason=Subscription.ClosedReason.PLAN_ENDED
    )
