"""Customer portal invoices (UI/UX 5.9, 6.x). Every lookup goes through the
scoped selector, so another customer's invoice id is a 404 (FR-1.7)."""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.accounts.permissions import Permission, require_permission

from . import selectors


@require_permission(Permission.VIEW_OWN_INVOICES)
def invoice_list(request):
    page = Paginator(selectors.customer_invoices(request.user), 25).get_page(
        request.GET.get("page")
    )
    return render(request, "billing/portal_invoice_list.html", {"page": page})


@require_permission(Permission.VIEW_OWN_INVOICES)
def invoice_detail(request, pk):
    invoice = get_object_or_404(selectors.customer_invoices(request.user), pk=pk)
    return render(request, "billing/portal_invoice_detail.html", {"invoice": invoice})


@require_permission(Permission.VIEW_OWN_INVOICES)
def invoice_print(request, pk):
    invoice = get_object_or_404(selectors.customer_invoices(request.user), pk=pk)
    back_url = reverse("portal_invoices:invoice_detail", args=[pk])
    return render(request, "billing/invoice_print.html", {"invoice": invoice, "back_url": back_url})
