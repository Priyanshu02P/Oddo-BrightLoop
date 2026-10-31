import hmac

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import Permission, require_permission

from . import dunning, selectors, services
from .exceptions import (
    InvoiceNotPayable,
    PaymentAmountMismatch,
    PaymentError,
    PaymentPending,
)
from .forms import PaymentForm
from .models import Payment

# Which form field a domain error belongs to; the rest go to the top of the form.
ERROR_FIELD = {
    PaymentAmountMismatch: "amount",
    InvoiceNotPayable: "invoice",
    PaymentPending: "invoice",
}


def _date_param(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def _without_page(params):
    params = params.copy()
    params.pop("page", None)
    return params.urlencode()


@require_permission(Permission.RECORD_PAYMENTS)
def payment_list(request):
    params = request.GET
    method = params.get("method") if params.get("method") in Payment.Method.values else None
    status = params.get("status") if params.get("status") in Payment.Status.values else None
    q = params.get("q", "").strip()
    date_from, date_to = _date_param(params.get("from")), _date_param(params.get("to"))
    payments = selectors.list_payments(
        q=q, method=method, status=status, date_from=date_from, date_to=date_to
    )
    context = {
        "page": Paginator(payments, 25).get_page(params.get("page")),
        "summary": selectors.receivables_summary(timezone.localdate()),
        "methods": Payment.Method.choices,
        "statuses": Payment.Status.choices,
        "filters": {
            "q": q,
            "method": method or "",
            "status": status or "",
            "from": date_from.isoformat() if date_from else "",
            "to": date_to.isoformat() if date_to else "",
        },
        "querystring": _without_page(params),
    }
    return render(request, "payments/payment_list.html", context)


def _result_message(request, payment):
    invoice = payment.invoice
    if payment.status == Payment.Status.SUCCEEDED:
        messages.success(
            request, f"Payment {payment.reference} recorded. Invoice {invoice.number} is now Paid."
        )
    elif payment.status == Payment.Status.PENDING:
        messages.warning(
            request,
            f"Payment {payment.reference} is pending at the gateway. Invoice "
            f"{invoice.number} stays unpaid until the gateway confirms it.",
        )
    else:
        messages.error(
            request,
            f"Payment {payment.reference} failed: {payment.failure_reason} "
            f"Invoice {invoice.number} is still unpaid.",
        )


@require_permission(Permission.RECORD_PAYMENTS)
@require_http_methods(["GET", "POST"])
def payment_create(request):
    mock_gateway = services.mock_gateway_enabled()
    initial = {}
    invoice_param = request.GET.get("invoice", "")
    if invoice_param.isdigit():
        invoice = selectors.payable_invoices().filter(pk=int(invoice_param)).first()
        if invoice is not None:
            initial = {"invoice": invoice, "amount": invoice.total}
    form = PaymentForm(request.POST or None, initial=initial, mock_gateway=mock_gateway)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            payment = services.record_payment(
                actor=request.user,
                invoice=data["invoice"],
                method=data["method"],
                amount=data["amount"],
                payment_date=data["payment_date"],
                note=data["note"],
                idempotency_key=data["idempotency_key"],
                simulated_outcome=data.get("simulated_outcome") or None,
            )
        except PaymentError as exc:
            form.add_error(ERROR_FIELD.get(type(exc)), str(exc))
        else:
            _result_message(request, payment)
            return redirect("payments:payment_detail", pk=payment.pk)
    totals = {str(i.pk): f"{i.total:.2f}" for i in form.fields["invoice"].queryset}
    context = {"form": form, "mock_gateway": mock_gateway, "invoice_totals": totals}
    return render(request, "payments/payment_form.html", context)


@require_permission(Permission.RECORD_PAYMENTS)
def payment_detail(request, pk):
    payment = get_object_or_404(selectors.payment_detail_queryset(), pk=pk)
    can_simulate = (
        payment.is_simulated
        and payment.status == Payment.Status.PENDING
        and services.mock_gateway_enabled()
    )
    return render(
        request, "payments/payment_detail.html", {"payment": payment, "can_simulate": can_simulate}
    )


@require_permission(Permission.RECORD_PAYMENTS)
@require_POST
def payment_resolve(request, pk, outcome):
    """Test mode only: play the gateway's late confirmation of a Pending payment."""
    if not services.mock_gateway_enabled() or outcome not in ("success", "failure"):
        raise Http404
    payment = get_object_or_404(Payment, pk=pk, method=Payment.Method.TEST_GATEWAY)
    try:
        payment = services.resolve_pending_payment(
            actor=request.user, payment=payment, succeeded=outcome == "success"
        )
    except PaymentError as exc:
        messages.error(request, str(exc))
    else:
        _result_message(request, payment)
    return redirect("payments:payment_detail", pk=pk)


@require_permission(Permission.RECORD_PAYMENTS)
def overdue_list(request):
    today = timezone.localdate()
    page = Paginator(selectors.overdue_invoices(today), 25).get_page(request.GET.get("page"))
    for invoice in page:
        invoice.days_late = (today - invoice.due_date).days
    context = {
        "page": page,
        "cadence": settings.DUNNING_CADENCE_DAYS,
        "stage_count": len(settings.DUNNING_CADENCE_DAYS),
    }
    return render(request, "payments/overdue_list.html", context)


@require_GET
def dunning_cron(request):
    """Vercel Cron entry point for overdue reminders (FR-7.8).

    Vercel Cron sends `Authorization: Bearer $CRON_SECRET` on a GET. The endpoint
    stays closed unless CRON_SECRET is set and matches.
    """
    expected = f"Bearer {settings.CRON_SECRET}" if settings.CRON_SECRET else None
    supplied = request.headers.get("Authorization", "")
    if expected is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
        return HttpResponse(status=403)
    return JsonResponse(dunning.run_dunning())
