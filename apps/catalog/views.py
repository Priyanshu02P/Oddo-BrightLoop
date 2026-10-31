from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import Permission, require_permission

from . import selectors, services
from .exceptions import StaleVariantData
from .forms import ProductForm, VariantFormSet
from .models import Product

STATUS_FILTERS = (selectors.STATUS_ACTIVE, selectors.STATUS_ARCHIVED)
STALE_VARIANTS_ERROR = (
    "The variants of this product were changed by someone else. Reload the page and try again."
)


@require_permission(Permission.MANAGE_CATALOG)
def product_list(request):
    status = request.GET.get("status")
    if status not in STATUS_FILTERS:
        status = None
    products = selectors.list_products(status)
    page = Paginator(products, 25).get_page(request.GET.get("page"))
    return render(request, "catalog/product_list.html", {"page": page, "status": status})


@require_permission(Permission.MANAGE_CATALOG)
def product_detail(request, pk):
    product = get_object_or_404(selectors.product_detail_queryset(), pk=pk)
    return render(request, "catalog/product_detail.html", {"product": product})


def _product_form_page(request, product=None):
    """Shared create/edit handler: the product and its variants are saved together."""
    instance = product or Product()
    data = request.POST if request.method == "POST" else None
    form = ProductForm(data, instance=instance)
    formset = VariantFormSet(data, instance=instance, prefix="variants")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        fields = {name: form.cleaned_data[name] for name in services.PRODUCT_FIELDS}
        try:
            if product is None:
                product = services.create_product(
                    actor=request.user, fields=fields, variants=formset.variant_rows()
                )
            else:
                product = services.update_product(
                    actor=request.user,
                    product=product,
                    fields=fields,
                    variants=formset.variant_rows(),
                )
        except StaleVariantData:
            form.add_error(None, STALE_VARIANTS_ERROR)
        else:
            messages.success(request, f"Product “{product.name}” saved.")
            return redirect("catalog:product_detail", pk=product.pk)
    context = {
        "form": form,
        "formset": formset,
        "product": product,
        "tax_exists": selectors.tax_exists(),
    }
    return render(request, "catalog/product_form.html", context)


@require_permission(Permission.MANAGE_CATALOG)
@require_http_methods(["GET", "POST"])
def product_create(request):
    return _product_form_page(request)


@require_permission(Permission.MANAGE_CATALOG)
@require_http_methods(["GET", "POST"])
def product_edit(request, pk):
    return _product_form_page(request, get_object_or_404(Product, pk=pk))


@require_permission(Permission.MANAGE_CATALOG)
@require_http_methods(["GET", "POST"])
def product_archive(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        services.archive_product(actor=request.user, product=product)
        messages.success(
            request,
            f"Product “{product.name}” archived. "
            "It is no longer offered for new subscription lines.",
        )
        return redirect("catalog:product_detail", pk=product.pk)
    return render(request, "catalog/product_archive.html", {"product": product})
