import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.permissions import Permission, has_permission

from .exceptions import StaleVariantData
from .models import PaymentTerm, Product, ProductVariant, Tax

logger = logging.getLogger(__name__)

PRODUCT_FIELDS = ("name", "type", "sales_price", "cost_price", "notes", "tax")
VARIANT_FIELDS = ("dimension", "value", "price_adjustment")


def _require_catalog_admin(actor):
    # Checked here as well as in the views, so the services are safe from any entry point.
    if not has_permission(actor, Permission.MANAGE_CATALOG):
        raise PermissionDenied


def _apply(instance, data, field_names):
    for name in field_names:
        setattr(instance, name, data[name])
    instance.full_clean()
    instance.save()


def _sync_variants(product, variants):
    """Make the product's variants match `variants` exactly.

    Each row is a dict of VARIANT_FIELDS plus an optional "id" of an existing
    variant of this product (updated in place). Rows without an id are created;
    existing variants not listed are removed.
    """
    existing = {variant.pk: variant for variant in product.variants.all()}
    kept = set()
    for row in variants:
        variant_id = row.get("id")
        if variant_id is None:
            variant = ProductVariant(product=product)
        elif variant_id in existing:
            variant = existing[variant_id]
            kept.add(variant_id)
        else:
            raise StaleVariantData
        _apply(variant, row, VARIANT_FIELDS)
    ProductVariant.objects.filter(pk__in=set(existing) - kept).delete()


def create_product(*, actor, fields, variants):
    """Create an active product and its variants atomically (FR-2.1, FR-2.2)."""
    _require_catalog_admin(actor)
    with transaction.atomic():
        product = Product()
        _apply(product, fields, PRODUCT_FIELDS)
        _sync_variants(product, variants)
    logger.info("Product %s created by user %s", product.pk, actor.pk)
    return product


def update_product(*, actor, product, fields, variants):
    """Update product fields and replace its variant set atomically.

    Only the catalog record changes; downstream subscription and invoice lines
    keep their own stored values and are not rewritten.
    """
    _require_catalog_admin(actor)
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product.pk)
        _apply(product, fields, PRODUCT_FIELDS)
        _sync_variants(product, variants)
    logger.info("Product %s updated by user %s", product.pk, actor.pk)
    return product


def archive_product(*, actor, product):
    """Archive instead of delete; safe to repeat. Archived products stay visible to Admin."""
    _require_catalog_admin(actor)
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product.pk)
        if product.is_archived:
            return product
        product.is_archived = True
        product.save(update_fields=["is_archived", "updated_at"])
    logger.info("Product %s archived by user %s", product.pk, actor.pk)
    return product


TAX_FIELDS = ("name", "rate")
PAYMENT_TERM_FIELDS = ("name", "days")


def _require_tax_admin(actor):
    if not has_permission(actor, Permission.MANAGE_TAXES_AND_PAYMENT_TERMS):
        raise PermissionDenied


def create_tax(*, actor, fields):
    """Create a Tax record (FR-9.1). Admin only."""
    _require_tax_admin(actor)
    tax = Tax()
    _apply(tax, fields, TAX_FIELDS)
    logger.info("Tax %s created by user %s", tax.pk, actor.pk)
    return tax


def update_tax(*, actor, tax, fields):
    """Update a Tax record. Admin only."""
    _require_tax_admin(actor)
    with transaction.atomic():
        tax = Tax.objects.select_for_update().get(pk=tax.pk)
        _apply(tax, fields, TAX_FIELDS)
    logger.info("Tax %s updated by user %s", tax.pk, actor.pk)
    return tax


def create_payment_term(*, actor, fields):
    """Create a PaymentTerm record (FR-9.3). Admin only."""
    _require_tax_admin(actor)
    term = PaymentTerm()
    _apply(term, fields, PAYMENT_TERM_FIELDS)
    logger.info("PaymentTerm %s created by user %s", term.pk, actor.pk)
    return term


def update_payment_term(*, actor, payment_term, fields):
    """Update a PaymentTerm record. Admin only."""
    _require_tax_admin(actor)
    with transaction.atomic():
        payment_term = PaymentTerm.objects.select_for_update().get(pk=payment_term.pk)
        _apply(payment_term, fields, PAYMENT_TERM_FIELDS)
    logger.info("PaymentTerm %s updated by user %s", payment_term.pk, actor.pk)
    return payment_term
