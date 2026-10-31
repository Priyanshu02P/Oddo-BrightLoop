"""Django admin registrations for M6 Discounts (read-only audit / data inspection)."""

from django.contrib import admin

from .models import Discount, DiscountProduct, DiscountRedemption, InvoiceDiscountSnapshot


class DiscountProductInline(admin.TabularInline):
    model = DiscountProduct
    extra = 0
    readonly_fields = ("created_at",)


class DiscountRedemptionInline(admin.TabularInline):
    model = DiscountRedemption
    extra = 0
    readonly_fields = ("customer", "usage_count", "created_at", "updated_at")
    can_delete = False


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "discount_type",
        "value",
        "scope_type",
        "start_date",
        "end_date",
        "usage_limit_per_customer",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "discount_type", "scope_type")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    inlines = [DiscountProductInline, DiscountRedemptionInline]


@admin.register(InvoiceDiscountSnapshot)
class InvoiceDiscountSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "discount_name",
        "discount_type",
        "amount_applied",
        "application_order",
        "redemption_confirmed",
    )
    list_filter = ("redemption_confirmed", "discount_type")
    readonly_fields = (
        "invoice",
        "discount",
        "discount_name",
        "discount_type",
        "discount_value",
        "scope_type",
        "application_order",
        "amount_applied",
        "redemption_confirmed",
    )
