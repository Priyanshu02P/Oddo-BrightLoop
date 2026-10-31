import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.permissions import Permission, require_permission
from apps.plans import selectors as plan_selectors
from apps.plans.exceptions import PlanNotAvailable
from apps.plans.models import Plan

from . import actions, selectors, services, tasks, template_services
from .exceptions import SubscriptionError
from .forms import SubscriptionCreateForm, SubscriptionLineForm, TemplateForm, TemplateLineFormSet
from .models import QuotationTemplate, Subscription, SubscriptionLine

logger = logging.getLogger(__name__)

DOMAIN_ERRORS = (SubscriptionError, PlanNotAvailable, ValidationError)


# --- Quotation templates (Admin only, FR-4.1) --------------------------------


@require_permission(Permission.MANAGE_QUOTATION_TEMPLATES)
def template_list(request):
    q = request.GET.get("q", "").strip()
    page = Paginator(selectors.list_templates(q), 25).get_page(request.GET.get("page"))
    return render(request, "subscriptions/template_list.html", {"page": page, "q": q})


def _template_form_page(request, template=None):
    instance = template or QuotationTemplate()
    data = request.POST if request.method == "POST" else None
    form = TemplateForm(data, instance=instance)
    formset = TemplateLineFormSet(data, instance=instance, prefix="lines")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        fields = {name: form.cleaned_data[name] for name in template_services.TEMPLATE_FIELDS}
        try:
            if template is None:
                template = template_services.create_quotation_template(
                    actor=request.user, fields=fields, lines=formset.line_rows()
                )
            else:
                template = template_services.update_quotation_template(
                    actor=request.user, template=template, fields=fields, lines=formset.line_rows()
                )
        except DOMAIN_ERRORS as exc:
            form.add_error(None, actions.error_text(exc))
        else:
            messages.success(request, f"Template “{template.name}” saved.")
            return redirect("subscriptions:template_list")
    context = {"form": form, "formset": formset, "quotation_template": template}
    return render(request, "subscriptions/template_form.html", context)


@require_permission(Permission.MANAGE_QUOTATION_TEMPLATES)
@require_http_methods(["GET", "POST"])
def template_create(request):
    return _template_form_page(request)


@require_permission(Permission.MANAGE_QUOTATION_TEMPLATES)
@require_http_methods(["GET", "POST"])
def template_edit(request, pk):
    return _template_form_page(request, get_object_or_404(QuotationTemplate, pk=pk))


# --- Subscriptions (Admin and Staff, FR-4.6) ---------------------------------


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
def subscription_list(request):
    params = request.GET
    status = params.get("status") if params.get("status") in Subscription.Status.values else None
    renewal = params.get("renewal_mode")
    if renewal not in Plan.RenewalMode.values:
        renewal = None
    plan_id = int(params["plan"]) if params.get("plan", "").isdigit() else None
    q = params.get("q", "").strip()
    subscriptions = selectors.list_subscriptions(
        status=status,
        plan_id=plan_id,
        renewal_mode=renewal,
        payment_failed=params.get("payment_failed") == "1",
        q=q,
    )
    all_subs = Subscription.objects.all()
    draft_count = all_subs.filter(status=Subscription.Status.DRAFT).count()
    quotation_count = all_subs.filter(status=Subscription.Status.QUOTATION).count()
    confirmed_count = all_subs.filter(status=Subscription.Status.CONFIRMED).count()
    active_count = all_subs.filter(status=Subscription.Status.ACTIVE).count()
    paused_count = all_subs.filter(status=Subscription.Status.PAUSED).count()
    closed_count = all_subs.filter(status=Subscription.Status.CLOSED).count()
    total_pipeline = (draft_count + quotation_count + confirmed_count + active_count + paused_count + closed_count) or 1

    upcoming_renewals = (
        Subscription.objects.filter(status=Subscription.Status.ACTIVE, next_billing_date__isnull=False)
        .select_related("customer__user", "plan")
        .order_by("next_billing_date")[:5]
    )

    context = {
        "page": Paginator(subscriptions, 25).get_page(params.get("page")),
        "statuses": Subscription.Status.choices,
        "plans": plan_selectors.list_plans(),
        "renewal_modes": Plan.RenewalMode.choices,
        "filters": {
            "status": status or "",
            "plan": plan_id,
            "renewal_mode": renewal or "",
            "payment_failed": params.get("payment_failed") == "1",
            "q": q,
        },
        "draft_count": draft_count,
        "quotation_count": quotation_count,
        "confirmed_count": confirmed_count,
        "active_count": active_count,
        "paused_count": paused_count,
        "closed_count": closed_count,
        "total_pipeline": total_pipeline,
        "upcoming_renewals": upcoming_renewals,
    }
    return render(request, "subscriptions/subscription_list.html", context)


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
@require_http_methods(["GET", "POST"])
def subscription_create(request):
    form = SubscriptionCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            subscription = services.create_subscription(
                actor=request.user,
                customer=data["customer"],
                plan=data["plan"],
                payment_terms=data["payment_terms"],
                start_date=data["start_date"],
                expiry_date=data["expiry_date"],
                template=data["template"],
            )
        except DOMAIN_ERRORS as exc:
            form.add_error(None, actions.error_text(exc))
        else:
            messages.success(request, f"Subscription {subscription.number} created as a Draft.")
            return redirect("subscriptions:subscription_detail", pk=subscription.pk)
    return render(request, "subscriptions/subscription_form.html", {"form": form})


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
def subscription_detail(request, pk):
    subscription = get_object_or_404(selectors.subscription_detail_queryset(), pk=pk)
    context = {
        "subscription": subscription,
        "activity": selectors.list_activity(subscription),
        "actions": actions.available_actions(subscription, internal=True),
        "editable": subscription.status == Subscription.Status.DRAFT,
    }
    return render(request, "subscriptions/subscription_detail.html", context)


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
@require_http_methods(["GET", "POST"])
def subscription_action(request, pk, action):
    subscription = get_object_or_404(
        Subscription.objects.select_related("customer__user", "plan"), pk=pk
    )
    return actions.run_action_page(
        request,
        subscription,
        action,
        allowed=actions.ACTIONS,
        detail_url=reverse("subscriptions:subscription_detail", args=[pk]),
    )


# --- Draft lines (FR-4.2, FR-4.12) -------------------------------------------


def _line_row(form):
    data = form.cleaned_data
    return {name: data[name] for name in ("product", "variant", "quantity", "is_addon")}


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
@require_http_methods(["GET", "POST"])
def line_form(request, pk, line_pk=None):
    subscription = get_object_or_404(Subscription, pk=pk)
    line = None
    if line_pk:
        line = get_object_or_404(SubscriptionLine, pk=line_pk, subscription=subscription)
    initial = (
        {
            "product": line.product_id,
            "variant": line.variant_id,
            "quantity": line.quantity,
            "is_addon": line.is_addon,
        }
        if line
        else None
    )
    form = SubscriptionLineForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            row = _line_row(form)
            if line is None:
                services.add_line(actor=request.user, subscription=subscription, row=row)
            else:
                services.update_line(actor=request.user, line=line, row=row)
        except DOMAIN_ERRORS as exc:
            form.add_error(None, actions.error_text(exc))
        else:
            messages.success(request, "Line saved.")
            return redirect("subscriptions:subscription_detail", pk=pk)
    context = {"form": form, "subscription": subscription, "line": line}
    return render(request, "subscriptions/line_form.html", context)


@require_permission(Permission.MANAGE_SUBSCRIPTIONS)
@require_http_methods(["POST"])
def line_remove(request, pk, line_pk):
    line = get_object_or_404(SubscriptionLine, pk=line_pk, subscription_id=pk)
    try:
        services.remove_line(actor=request.user, line=line)
    except DOMAIN_ERRORS as exc:
        messages.error(request, actions.error_text(exc))
    else:
        messages.success(request, "Line removed.")
    return redirect("subscriptions:subscription_detail", pk=pk)


# --- Scheduled jobs (FR-10.1) --------------------------------------------------


@require_GET
def daily_cron(request):
    """Vercel Cron entry point: quotation expiry, then activation of due subscriptions.

    Vercel Cron sends `Authorization: Bearer $CRON_SECRET` on a GET. The endpoint
    stays closed unless CRON_SECRET is set and matches.
    """
    expected = f"Bearer {settings.CRON_SECRET}" if settings.CRON_SECRET else None
    supplied = request.headers.get("Authorization", "")
    if expected is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
        return HttpResponse(status=403)
    return JsonResponse(
        {
            "expired": tasks.expire_quotations(),
            "activated": tasks.activate_due_subscriptions(),
        }
    )
