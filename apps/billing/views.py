import hmac

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import Permission, require_permission

from . import actions, billing_runs, selectors, tasks
from .exceptions import BillingError
from .models import BillingRun, BillingRunResult, Invoice


def _date_param(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def _without_page(params):
    """Current filters as a query string, for the pagination links."""
    params = params.copy()
    params.pop("page", None)
    return params.urlencode()


# --- Invoices (Admin and Staff, UI/UX 5.9) -------------------------------------


@require_permission(Permission.MANAGE_INVOICES)
def invoice_list(request):
    params = request.GET
    status = params.get("status") if params.get("status") in Invoice.Status.values else None
    overdue = params.get("overdue") == "1"
    q = params.get("q", "").strip()
    date_from, date_to = _date_param(params.get("from")), _date_param(params.get("to"))
    invoices = selectors.list_invoices(
        status=status,
        overdue_on=timezone.localdate() if overdue else None,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
    from decimal import Decimal
    from django.db.models import Sum

    today = timezone.localdate()
    all_invoices = Invoice.objects.all()
    open_count = all_invoices.filter(status__in=[Invoice.Status.DRAFT, Invoice.Status.CONFIRMED]).count()
    paid_count = all_invoices.filter(status=Invoice.Status.PAID).count()
    confirmed_count = all_invoices.filter(status=Invoice.Status.CONFIRMED).count()
    draft_count = all_invoices.filter(status=Invoice.Status.DRAFT).count()
    cancelled_count = all_invoices.filter(status=Invoice.Status.CANCELLED).count()
    overdue_count = all_invoices.filter(status=Invoice.Status.CONFIRMED, due_date__lt=today).count()

    outstanding_sum = all_invoices.filter(status=Invoice.Status.CONFIRMED).aggregate(t=Sum("total"))["t"] or Decimal("0.00")
    overdue_sum = all_invoices.filter(status=Invoice.Status.CONFIRMED, due_date__lt=today).aggregate(t=Sum("total"))["t"] or Decimal("0.00")

    total_stat = (paid_count + confirmed_count + draft_count + cancelled_count) or 1
    pct_paid = round((paid_count / total_stat) * 100, 1)
    pct_confirmed = round((confirmed_count / total_stat) * 100, 1)
    pct_draft = round((draft_count / total_stat) * 100, 1)
    pct_cancelled = round((cancelled_count / total_stat) * 100, 1)

    deg_paid = int(round(pct_paid * 3.6))
    deg_conf = deg_paid + int(round(pct_confirmed * 3.6))
    deg_draft = deg_conf + int(round(pct_draft * 3.6))

    context = {
        "page": Paginator(invoices, 25).get_page(params.get("page")),
        "statuses": Invoice.Status.choices,
        "filters": {
            "status": status or "",
            "overdue": overdue,
            "q": q,
            "from": date_from.isoformat() if date_from else "",
            "to": date_to.isoformat() if date_to else "",
        },
        "querystring": _without_page(params),
        "open_count": open_count,
        "paid_count": paid_count,
        "confirmed_count": confirmed_count,
        "draft_count": draft_count,
        "cancelled_count": cancelled_count,
        "overdue_count": overdue_count,
        "outstanding_sum": outstanding_sum,
        "overdue_sum": overdue_sum,
        "total_stat": total_stat,
        "pct_paid": pct_paid,
        "pct_confirmed": pct_confirmed,
        "pct_draft": pct_draft,
        "pct_cancelled": pct_cancelled,
        "deg_paid": deg_paid,
        "deg_conf": deg_conf,
        "deg_draft": deg_draft,
    }
    return render(request, "billing/invoice_list.html", context)


@require_permission(Permission.MANAGE_INVOICES)
def invoice_detail(request, pk):
    invoice = get_object_or_404(selectors.invoice_detail_queryset(), pk=pk)
    context = {
        "invoice": invoice,
        "actions": actions.available_actions(invoice),
        "activity": selectors.list_activity(invoice),
    }
    return render(request, "billing/invoice_detail.html", context)


@require_permission(Permission.MANAGE_INVOICES)
@require_http_methods(["GET", "POST"])
def invoice_action(request, pk, action):
    """GET shows a confirmation page naming the invoice and total; POST acts (UI/UX 4.5)."""
    if action not in actions.ACTIONS:
        raise Http404
    invoice = get_object_or_404(Invoice.objects.select_related("subscription"), pk=pk)
    chosen = actions.ACTIONS[action]
    if request.method == "POST":
        try:
            result = chosen.service(actor=request.user, invoice=invoice)
        except BillingError as exc:
            messages.error(request, str(exc))
        else:
            if result is False:  # send_invoice: the mail server refused it
                messages.error(
                    request,
                    "The email could not be sent. The invoice is unchanged; try sending it again.",
                )
            else:
                messages.success(request, chosen.success)
        return redirect("billing:invoice_detail", pk=pk)
    return render(request, "billing/invoice_action.html", {"invoice": invoice, "action": chosen})


@require_permission(Permission.MANAGE_INVOICES)
def invoice_print(request, pk):
    invoice = get_object_or_404(selectors.invoice_detail_queryset(), pk=pk)
    back_url = reverse("billing:invoice_detail", args=[pk])
    return render(request, "billing/invoice_print.html", {"invoice": invoice, "back_url": back_url})


# --- Billing runs (Admin and Staff, UI/UX 5.10) ----------------------------------


@require_permission(Permission.RUN_BILLING)
def run_list(request):
    page = Paginator(selectors.list_runs(), 25).get_page(request.GET.get("page"))
    running = selectors.running_run()
    last_run = BillingRun.objects.order_by("-started_at").first()
    last_run_counts = selectors.run_with_counts(last_run.pk) if last_run else None

    from apps.billing.models import BillingRunResult
    failures = (
        BillingRunResult.objects.filter(outcome="failed")
        .select_related("subscription__customer__user", "run")
        .order_by("-created_at")[:4]
    )

    return render(
        request,
        "billing/run_list.html",
        {
            "page": page,
            "running": running,
            "last_run": last_run,
            "last_run_counts": last_run_counts,
            "failures": failures,
        },
    )


def _report_run(request, run):
    counts = selectors.run_with_counts(run.pk)
    summary = (
        f"{counts.created} invoices created, {counts.skipped} skipped, {counts.failed} failed."
    )
    if run.status == BillingRun.Status.RUNNING:
        messages.warning(
            request,
            f"Billing run paused to stay within the time limit: {summary} "
            "Continue it now, or the next scheduled run will finish it.",
        )
    else:
        messages.success(request, f"Billing run finished: {summary}")
    return redirect("billing:run_detail", pk=run.pk)


@require_permission(Permission.RUN_BILLING)
@require_POST
def run_start(request):
    run = billing_runs.start_manual_run(
        actor=request.user, today=timezone.localdate(), deadline=billing_runs.deadline_from_now()
    )
    return _report_run(request, run)


@require_permission(Permission.RUN_BILLING)
@require_POST
def run_continue(request, pk):
    run = get_object_or_404(BillingRun, pk=pk)
    run = billing_runs.continue_run(
        actor=request.user, run=run, deadline=billing_runs.deadline_from_now()
    )
    return _report_run(request, run)


@require_permission(Permission.RUN_BILLING)
def run_detail(request, pk):
    try:
        run = selectors.run_with_counts(pk)
    except BillingRun.DoesNotExist:
        raise Http404 from None
    outcome = request.GET.get("outcome")
    if outcome not in BillingRunResult.Outcome.values:
        outcome = None
    results = selectors.run_results(run, outcome)
    context = {
        "run": run,
        "outcome": outcome,
        "outcomes": BillingRunResult.Outcome.choices,
        "page": Paginator(results, 50).get_page(request.GET.get("page")),
    }
    return render(request, "billing/run_detail.html", context)


# --- Scheduler (FR-10.1) ----------------------------------------------------------


@require_GET
def billing_cron(request):
    """Vercel Cron entry point for the scheduled billing run.

    Vercel Cron sends `Authorization: Bearer $CRON_SECRET` on a GET. The endpoint
    stays closed unless CRON_SECRET is set and matches.
    """
    expected = f"Bearer {settings.CRON_SECRET}" if settings.CRON_SECRET else None
    supplied = request.headers.get("Authorization", "")
    if expected is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
        return HttpResponse(status=403)
    return JsonResponse(tasks.run_scheduled_billing())
