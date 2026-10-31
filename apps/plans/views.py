import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.permissions import Permission, require_permission

from . import selectors, services, tasks
from .forms import PlanForm
from .models import Plan

logger = logging.getLogger(__name__)


@require_permission(Permission.MANAGE_CATALOG)
def plan_list(request):
    page = Paginator(selectors.list_plans(), 25).get_page(request.GET.get("page"))
    return render(request, "plans/plan_list.html", {"page": page})


@require_permission(Permission.MANAGE_CATALOG)
def plan_detail(request, pk):
    return render(request, "plans/plan_detail.html", {"plan": get_object_or_404(Plan, pk=pk)})


def _plan_form_page(request, plan=None):
    """Shared create/edit handler."""
    data = request.POST if request.method == "POST" else None
    form = PlanForm(data, instance=plan or Plan())
    if request.method == "POST" and form.is_valid():
        fields = {name: form.cleaned_data[name] for name in services.PLAN_FIELDS}
        if plan is None:
            plan = services.create_plan(actor=request.user, fields=fields)
        else:
            plan = services.update_plan(actor=request.user, plan=plan, fields=fields)
        messages.success(request, f"Plan “{plan.name}” saved.")
        return redirect("plans:plan_detail", pk=plan.pk)
    return render(request, "plans/plan_form.html", {"form": form, "plan": plan})


@require_permission(Permission.MANAGE_CATALOG)
@require_http_methods(["GET", "POST"])
def plan_create(request):
    return _plan_form_page(request)


@require_permission(Permission.MANAGE_CATALOG)
@require_http_methods(["GET", "POST"])
def plan_edit(request, pk):
    return _plan_form_page(request, get_object_or_404(Plan, pk=pk))


@require_GET
def auto_close_cron(request):
    """Vercel Cron entry point for plan auto-close (FR-3.6, FR-10.1).

    Vercel Cron sends `Authorization: Bearer $CRON_SECRET` on a GET. The
    endpoint is closed unless CRON_SECRET is set and matches. The subscription
    closer is supplied by M4 through PLANS_AUTO_CLOSE_HANDLER.
    """
    expected = f"Bearer {settings.CRON_SECRET}" if settings.CRON_SECRET else None
    supplied = request.headers.get("Authorization", "")
    if expected is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
        return HttpResponse(status=403)
    if not settings.PLANS_AUTO_CLOSE_HANDLER:
        logger.error("Plan auto-close ran but PLANS_AUTO_CLOSE_HANDLER is not configured.")
        return JsonResponse({"error": "Auto-close handler is not configured."}, status=503)
    handler = import_string(settings.PLANS_AUTO_CLOSE_HANDLER)
    return JsonResponse(tasks.run_auto_close(handler))
