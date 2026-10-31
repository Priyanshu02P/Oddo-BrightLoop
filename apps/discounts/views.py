"""Thin views for M6 Discounts. Views parse the request, call services/selectors,
and return a response. No business logic here (CODING_STANDARDS §1.3).
"""

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.permissions import Permission, require_permission

from . import selectors, services
from .exceptions import InvalidDiscountRule
from .forms import DiscountForm
from .models import Discount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@require_permission(Permission.CREATE_DISCOUNT_RULES)
def discount_list(request):
    """Paginated list of all discount rules (Admin only)."""
    q = request.GET.get("q", "").strip()
    is_active_param = request.GET.get("is_active", "")
    is_active = None
    if is_active_param == "1":
        is_active = True
    elif is_active_param == "0":
        is_active = False

    discounts = selectors.list_discounts(is_active=is_active, q=q)
    page = Paginator(discounts, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "discounts/discount_list.html",
        {
            "page": page,
            "q": q,
            "is_active_filter": is_active_param,
        },
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@require_permission(Permission.CREATE_DISCOUNT_RULES)
def discount_detail(request, pk):
    """Discount rule detail page with redemption info (Admin only)."""
    discount = get_object_or_404(selectors.discount_detail_queryset(), pk=pk)
    summary = selectors.redemption_summary(discount)
    return render(
        request,
        "discounts/discount_detail.html",
        {
            "discount": discount,
            "redemption_summary": summary,
        },
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@require_permission(Permission.CREATE_DISCOUNT_RULES)
@require_http_methods(["GET", "POST"])
def discount_create(request):
    """Create a new discount rule (Admin only)."""
    form = DiscountForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        try:
            discount = services.create_discount(actor=request.user, data=data)
        except InvalidDiscountRule as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Discount \u201c{discount.name}\u201d created.")
            return redirect("discounts:discount_detail", pk=discount.pk)
    return render(request, "discounts/discount_form.html", {"form": form, "discount": None})


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


@require_permission(Permission.CREATE_DISCOUNT_RULES)
@require_http_methods(["GET", "POST"])
def discount_edit(request, pk):
    """Edit an existing discount rule (Admin only)."""
    discount = get_object_or_404(Discount, pk=pk)
    form = DiscountForm(request.POST if request.method == "POST" else None, instance=discount)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        try:
            discount = services.update_discount(actor=request.user, discount=discount, data=data)
        except InvalidDiscountRule as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Discount \u201c{discount.name}\u201d updated.")
            return redirect("discounts:discount_detail", pk=discount.pk)
    return render(request, "discounts/discount_form.html", {"form": form, "discount": discount})


# ---------------------------------------------------------------------------
# Preview (illustrative — does NOT touch redemptions or invoice data)
# ---------------------------------------------------------------------------


@require_permission(Permission.CREATE_DISCOUNT_RULES)
@require_POST
def discount_preview(request):
    """Return a JSON preview of how a discount type/value applies to a sample amount.

    POST body (form-encoded or JSON):
      - discount_type: "fixed" or "percentage"
      - value: decimal string
      - example_amount: decimal string (the eligible amount to illustrate against)

    This is purely illustrative and creates no database records.
    """
    try:
        discount_type = request.POST.get("discount_type", "")
        value_str = request.POST.get("value", "")
        amount_str = request.POST.get("example_amount", "1000.00")
        value = Decimal(value_str)
        eligible = Decimal(amount_str)
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "Invalid numeric input."}, status=400)

    if discount_type not in (Discount.DiscountType.FIXED_AMOUNT, Discount.DiscountType.PERCENTAGE):
        return JsonResponse({"error": "Invalid discount_type."}, status=400)

    from apps.subscriptions.pricing import round_money

    ZERO_D = Decimal("0.00")

    if discount_type == Discount.DiscountType.FIXED_AMOUNT:
        applied = min(value, eligible)
    else:
        applied = round_money(eligible * value / Decimal("100"))
        applied = min(applied, eligible)

    remaining = max(ZERO_D, eligible - applied)

    return JsonResponse(
        {
            "eligible_amount": str(eligible),
            "discount_type": discount_type,
            "discount_value": str(value),
            "amount_applied": str(applied),
            "remaining_amount": str(remaining),
            "note": "Illustrative preview only. Not a quote or invoice.",
        }
    )
