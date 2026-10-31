"""Read-only queries for M6 Discounts (selectors pattern, CODING_STANDARDS §1.3)."""

from django.db.models import Count, Prefetch, Q

from .models import Discount, DiscountProduct, DiscountRedemption, InvoiceDiscountSnapshot


def list_discounts(*, is_active=None, q=""):
    """Admin list: ordered, filterable, with prefetched product names."""
    qs = Discount.objects.select_related("created_by", "updated_by")
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if q:
        qs = qs.filter(Q(name__icontains=q))
    return qs.order_by("-created_at", "-id")


def discount_detail_queryset():
    """Single discount with all related data for the detail view."""
    return Discount.objects.select_related("created_by", "updated_by").prefetch_related(
        Prefetch(
            "discount_products",
            queryset=DiscountProduct.objects.select_related("product").order_by("id"),
        ),
        Prefetch(
            "redemptions",
            queryset=DiscountRedemption.objects.select_related("customer__user").order_by(
                "-usage_count", "id"
            ),
        ),
    )


def get_customer_usage(*, discount, customer):
    """Return the customer's confirmed usage count for a discount, or 0 if no record."""
    try:
        redemption = DiscountRedemption.objects.get(discount=discount, customer=customer)
        return redemption.usage_count
    except DiscountRedemption.DoesNotExist:
        return 0


def redemption_summary(discount):
    """Aggregate redemption stats for a discount (for detail view)."""
    return DiscountRedemption.objects.filter(discount=discount).aggregate(
        total_customers=Count("id"),
    )


def snapshots_for_invoice(invoice):
    """Ordered discount snapshots for an invoice."""
    return (
        InvoiceDiscountSnapshot.objects.filter(invoice=invoice)
        .select_related("discount")
        .order_by("application_order", "id")
    )
