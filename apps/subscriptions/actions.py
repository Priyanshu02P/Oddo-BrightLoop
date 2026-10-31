"""Lifecycle actions shared by the internal screens and the customer portal.

The table drives the confirmation page and the action buttons only. Whether an
action is really allowed is decided by the service it calls.
"""

from dataclasses import dataclass

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render

from apps.plans.exceptions import PlanNotAvailable

from . import services
from .exceptions import SubscriptionError
from .models import Subscription

Status = Subscription.Status


@dataclass(frozen=True)
class Action:
    label: str
    service: object
    explanation: str
    success: str
    danger: bool = False


ACTIONS = {
    "send": Action(
        "Send quotation",
        services.send_quotation,
        "The customer is emailed and the quotation becomes open for acceptance until its "
        "validity date. Lines can no longer be edited.",
        "Quotation sent.",
    ),
    "accept": Action(
        "Accept quotation",
        services.accept_quotation,
        "The subscription becomes Confirmed and starts on its start date.",
        "Quotation accepted.",
    ),
    "pause": Action(
        "Pause",
        services.pause_subscription,
        "A paused subscription is excluded from billing runs until it is resumed.",
        "Subscription paused.",
    ),
    "resume": Action(
        "Resume",
        services.resume_subscription,
        "The subscription becomes Active and its next billing date is recalculated.",
        "Subscription resumed.",
    ),
    "cancel": Action(
        "Close subscription",
        services.cancel_subscription,
        "The subscription is closed and can't be reopened. Its history stays visible.",
        "Subscription closed.",
        danger=True,
    ),
}

PORTAL_ACTIONS = ("accept", "pause", "resume", "cancel")


def available_actions(subscription, *, internal):
    """Keys of the buttons worth showing for this status and plan (UI only)."""
    plan, keys = subscription.plan, []
    if subscription.status == Status.DRAFT and internal:
        keys.append("send")
    if subscription.status == Status.QUOTATION:
        keys.append("accept")
    if subscription.status == Status.ACTIVE and plan.allow_pause:
        keys.append("pause")
    if subscription.status == Status.PAUSED:
        keys.append("resume")
    if subscription.status in (Status.ACTIVE, Status.PAUSED) and plan.allow_close_early:
        keys.append("cancel")
    return [(key, ACTIONS[key]) for key in keys]


def error_text(exc):
    return " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)


def run_action_page(request, subscription, key, *, allowed, detail_url):
    """GET shows a confirmation page, POST runs the action (UI/UX 4.5)."""
    if key not in allowed:
        raise Http404
    action = ACTIONS[key]
    if request.method == "POST":
        try:
            action.service(actor=request.user, subscription=subscription)
        except (SubscriptionError, PlanNotAvailable, ValidationError) as exc:
            messages.error(request, error_text(exc))
        else:
            messages.success(request, action.success)
        return redirect(detail_url)
    context = {
        "subscription": subscription,
        "action": action,
        "detail_url": detail_url,
    }
    return render(request, "subscriptions/action_confirm.html", context)
