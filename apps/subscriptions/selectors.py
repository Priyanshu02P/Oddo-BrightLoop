from django.db.models import Count, Q

from apps.accounts.models import AuditLog
from apps.accounts.permissions import scope_to_customer

from .models import QuotationTemplate, Subscription


def list_subscriptions(*, status=None, plan_id=None, renewal_mode=None, payment_failed=None, q=""):
    """Internal list (FR-4.6): joins done up front so a page is a fixed number of queries."""
    subscriptions = Subscription.objects.select_related("customer__user", "plan")
    if status:
        subscriptions = subscriptions.filter(status=status)
    if plan_id:
        subscriptions = subscriptions.filter(plan_id=plan_id)
    if renewal_mode:
        subscriptions = subscriptions.filter(plan__renewal_mode=renewal_mode)
    if payment_failed:
        subscriptions = subscriptions.filter(payment_failed=True)
    if q:
        subscriptions = subscriptions.filter(
            Q(number__icontains=q) | Q(customer__user__email__icontains=q)
        )
    return subscriptions.order_by("-id")


def subscription_detail_queryset():
    return Subscription.objects.select_related(
        "customer__user", "plan", "payment_terms"
    ).prefetch_related("lines__product", "lines__variant")


def customer_subscriptions(user):
    """Every customer-facing read goes through here: scoped to the signed-in
    customer, so an id from another customer is simply not found (FR-1.7)."""
    return scope_to_customer(subscription_detail_queryset(), user).order_by("-id")


def list_activity(subscription):
    return (
        AuditLog.objects.select_related("actor")
        .filter(target_type=subscription._meta.label_lower, target_id=subscription.pk)
        .order_by("created_at", "id")
    )


def list_templates(q=""):
    templates = QuotationTemplate.objects.select_related("plan").annotate(line_count=Count("lines"))
    if q:
        templates = templates.filter(name__icontains=q)
    return templates.order_by("name", "id")


def due_for_expiry(today):
    return Subscription.objects.filter(status=Subscription.Status.QUOTATION, valid_until__lt=today)


def due_for_activation(today):
    return Subscription.objects.filter(status=Subscription.Status.CONFIRMED, start_date__lte=today)


def open_for_plan(plan):
    return Subscription.objects.filter(
        plan=plan, status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAUSED]
    )
