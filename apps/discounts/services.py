"""Business logic for M6 Discounts (FR-6.1 – FR-6.9, BR-9, BR-10).

Service layer owns all write-side operations and the stacking engine.
M5 calls apply_stacked_discounts() during invoice generation and
record_confirmed_redemptions() during confirm_invoice().
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission
from apps.subscriptions.pricing import round_money

from .exceptions import DiscountRedemptionConflict, InvalidDiscountRule
from .models import Discount, DiscountProduct, DiscountRedemption, InvoiceDiscountSnapshot

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require(actor, permission=Permission.CREATE_DISCOUNT_RULES):
    """Defense-in-depth: service also checks permission, not just the view."""
    if not has_permission(actor, permission):
        raise PermissionDenied


def _set_products(discount, product_ids):
    """Replace the DiscountProduct rows for a discount atomically."""
    existing = set(
        DiscountProduct.objects.filter(discount=discount).values_list("product_id", flat=True)
    )
    new_ids = set(product_ids)
    to_delete = existing - new_ids
    to_add = new_ids - existing
    if to_delete:
        DiscountProduct.objects.filter(discount=discount, product_id__in=to_delete).delete()
    if to_add:
        DiscountProduct.objects.bulk_create(
            [DiscountProduct(discount=discount, product_id=pid) for pid in sorted(to_add)]
        )


# ---------------------------------------------------------------------------
# CRUD services (FR-6.1)
# ---------------------------------------------------------------------------


def create_discount(*, actor, data):
    """Create a new discount rule. `data` must be a validated dict from DiscountForm.

    Args:
        actor: The User creating the discount (must have CREATE_DISCOUNT_RULES).
        data: Dict with keys matching Discount fields plus optional 'products' list.

    Returns:
        The created Discount instance.
    """
    _require(actor)
    product_ids = data.pop("products", [])
    if data.get("value") is not None and data["value"] <= ZERO:
        raise InvalidDiscountRule("Discount value must be positive.")
    with transaction.atomic():
        discount = Discount.objects.create(**data, created_by=actor)
        if discount.scope_type == Discount.ScopeType.SELECTED_PRODUCTS:
            _set_products(discount, [p.pk if hasattr(p, "pk") else p for p in product_ids])
    record_audit(actor=actor, action="discount.created", target=discount)
    logger.info("Discount %s created by %s", discount.pk, actor.pk)
    return discount


def update_discount(*, actor, discount, data):
    """Update an existing discount rule.

    Args:
        actor: The User editing the discount.
        discount: The Discount instance to update.
        data: Dict with updated fields plus optional 'products' list.

    Returns:
        The updated Discount instance.
    """
    _require(actor)
    product_ids = data.pop("products", [])
    if data.get("value") is not None and data["value"] <= ZERO:
        raise InvalidDiscountRule("Discount value must be positive.")
    with transaction.atomic():
        for attr, value in data.items():
            setattr(discount, attr, value)
        discount.updated_by = actor
        discount.save()
        if discount.scope_type == Discount.ScopeType.SELECTED_PRODUCTS:
            _set_products(discount, [p.pk if hasattr(p, "pk") else p for p in product_ids])
        else:
            # WHOLE_SUBSCRIPTION: remove any lingering product links
            DiscountProduct.objects.filter(discount=discount).delete()
    record_audit(actor=actor, action="discount.updated", target=discount)
    logger.info("Discount %s updated by %s", discount.pk, actor.pk)
    return discount


# ---------------------------------------------------------------------------
# Eligibility (FR-6.3, FR-6.4, FR-6.6)
# ---------------------------------------------------------------------------


@dataclass
class _LineInfo:
    """Internal: pre-computed data for one invoice line used during eligibility."""

    index: int
    pk: int | None
    product_id: int
    amount: Decimal
    quantity: int


def _build_line_infos(invoice_lines):
    """Convert invoice lines (InvoiceLine instances) to lightweight _LineInfo objects."""
    return [
        _LineInfo(
            index=i,
            pk=getattr(line, "pk", None),
            product_id=line.product_id
            or (line.product.pk if hasattr(line, "product") and line.product else None),
            amount=line.amount,
            quantity=line.quantity,
        )
        for i, line in enumerate(invoice_lines)
    ]


def _matching_line_indices(discount, line_infos):
    """Return indices of line_infos that match the discount's scope."""
    if discount.scope_type == Discount.ScopeType.WHOLE_SUBSCRIPTION:
        return [li.index for li in line_infos]

    # SELECTED_PRODUCTS
    product_ids = set(
        DiscountProduct.objects.filter(discount=discount).values_list("product_id", flat=True)
    )
    return [li.index for li in line_infos if li.product_id in product_ids]


def _passes_eligibility(*, discount, customer, line_infos, as_of):
    """Return (passes: bool, reason: str) for a single discount.

    Reasons are logged but never raised to the caller: ineligible discounts are
    skipped silently per FR-5.9.
    """
    # 1. is_active flag
    if not discount.is_active:
        return False, "discount is inactive"

    # 2. Date window (inclusive both ends, per working assumption)
    if as_of < discount.start_date:
        return False, f"discount not yet active (starts {discount.start_date})"
    if as_of > discount.end_date:
        return False, f"discount expired ({discount.end_date})"

    # 3. Per-customer usage limit
    try:
        redemption = DiscountRedemption.objects.get(discount=discount, customer=customer)
        usage = redemption.usage_count
    except DiscountRedemption.DoesNotExist:
        usage = 0
    if usage >= discount.usage_limit_per_customer:
        return False, (
            f"customer usage limit reached ({usage}/{discount.usage_limit_per_customer})"
        )

    # 4 & 5. Scope and Minimum conditions — AND logic
    matching_indices = set(_matching_line_indices(discount, line_infos))
    if not matching_indices:
        return False, "no lines matching discount product scope"

    matching_lines = [li for li in line_infos if li.index in matching_indices]
    eligible_amount = sum((li.amount for li in matching_lines), ZERO)

    if discount.minimum_purchase_amount is not None:
        if eligible_amount < discount.minimum_purchase_amount:
            return False, (
                f"minimum purchase amount not met "
                f"({eligible_amount} < {discount.minimum_purchase_amount})"
            )

    if discount.minimum_quantity is not None:
        qty = sum(li.quantity for li in matching_lines)
        if qty < discount.minimum_quantity:
            return False, (f"minimum quantity not met ({qty} < {discount.minimum_quantity})")

    return True, ""


def get_eligible_discounts(*, customer, subscription, invoice_lines, as_of):
    """Return active Discount instances eligible for this invoice context.

    Args:
        customer: Customer instance.
        subscription: Subscription instance.
        invoice_lines: Iterable of InvoiceLine instances with .pk, .product_id,
                       .amount, .quantity.
        as_of: date — the invoice generation date used for eligibility checks.

    Returns:
        List of Discount instances that pass all eligibility conditions.
    """
    candidates = Discount.objects.filter(
        is_active=True,
        start_date__lte=as_of,
        end_date__gte=as_of,
    ).order_by("id")

    line_infos = _build_line_infos(invoice_lines)
    eligible = []
    for discount in candidates:
        passes, reason = _passes_eligibility(
            discount=discount, customer=customer, line_infos=line_infos, as_of=as_of
        )
        if passes:
            eligible.append(discount)
        else:
            logger.info(
                "Discount %s skipped for customer %s / subscription %s: %s",
                discount.pk,
                customer.pk,
                subscription.pk if subscription else None,
                reason,
            )
    return eligible


# ---------------------------------------------------------------------------
# Stacking engine (FR-6.7, FR-6.9, BR-9)
# ---------------------------------------------------------------------------


@dataclass
class DiscountApplication:
    """Result of applying one discount within the stacking calculation."""

    discount: Discount
    amount_applied: Decimal
    affected_line_pks: list = field(default_factory=list)


@dataclass
class DiscountApplicationResult:
    """Full result returned to M5 after running the stacking engine."""

    applications: list  # list[DiscountApplication]
    total_discount: Decimal
    line_discounts: dict = field(default_factory=dict)  # {line_index: Decimal}


def apply_stacked_discounts(*, subscription, customer, invoice_lines, as_of):
    """Apply eligible discounts in the required stacking order (FR-6.9, BR-9).

    Stacking order:
      1. Fixed-amount discounts, ascending id (deterministic tie-break).
      2. Percentage discounts on the remaining amount, ascending id.

    The combined discount is capped at 100% of the eligible amount (BR-9).
    Amounts are allocated across matching lines proportionally to their remaining
    balance and rounded per line, reconciling with total_discount.

    Args:
        subscription: Subscription instance.
        customer: Customer instance.
        invoice_lines: Iterable of InvoiceLine instances.
        as_of: date for eligibility evaluation.

    Returns:
        DiscountApplicationResult with applications, total_discount, and line_discounts.
    """
    try:
        eligible = get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=invoice_lines,
            as_of=as_of,
        )
    except Exception as exc:
        logger.exception(
            "Error evaluating discounts for subscription %s: %s",
            getattr(subscription, "pk", None),
            exc,
        )
        return DiscountApplicationResult(applications=[], total_discount=ZERO, line_discounts={})

    if not eligible:
        return DiscountApplicationResult(applications=[], total_discount=ZERO, line_discounts={})

    line_infos = _build_line_infos(invoice_lines)
    line_remaining = {li.index: li.amount for li in line_infos}
    line_discounts = {li.index: ZERO for li in line_infos}

    # Sort: fixed first (by id), then percentage (by id) — FR-6.9.
    fixed = sorted(
        [d for d in eligible if d.discount_type == Discount.DiscountType.FIXED_AMOUNT],
        key=lambda d: d.id,
    )
    percentage = sorted(
        [d for d in eligible if d.discount_type == Discount.DiscountType.PERCENTAGE],
        key=lambda d: d.id,
    )

    ordered = fixed + percentage
    applications = []

    for discount in ordered:
        matching_indices = [
            idx
            for idx in _matching_line_indices(discount, line_infos)
            if line_remaining[idx] > ZERO
        ]
        if not matching_indices:
            continue

        scope_remaining = sum((line_remaining[idx] for idx in matching_indices), ZERO)
        if scope_remaining <= ZERO:
            continue

        if discount.discount_type == Discount.DiscountType.FIXED_AMOUNT:
            applied = min(discount.value, scope_remaining)
        else:
            raw = round_money(scope_remaining * discount.value / Decimal("100"))
            applied = min(raw, scope_remaining)

        if applied <= ZERO:
            continue

        # Allocate `applied` proportionally across matching lines
        allocated = ZERO
        shares = {}
        for idx in matching_indices:
            share = round_money(applied * line_remaining[idx] / scope_remaining)
            share = min(share, line_remaining[idx])
            shares[idx] = share
            allocated += share

        diff = applied - allocated
        if diff != ZERO:
            target_idx = max(matching_indices, key=lambda i: line_remaining[i])
            adjusted = shares[target_idx] + diff
            if ZERO <= adjusted <= line_remaining[target_idx]:
                shares[target_idx] = adjusted
            else:
                applied = allocated

        for idx, share in shares.items():
            line_discounts[idx] += share
            line_remaining[idx] = max(ZERO, line_remaining[idx] - share)

        matching_pks = [
            line_infos[idx].pk for idx in matching_indices if line_infos[idx].pk is not None
        ]
        applications.append(
            DiscountApplication(
                discount=discount,
                amount_applied=applied,
                affected_line_pks=matching_pks,
            )
        )

    total = sum((app.amount_applied for app in applications), ZERO)
    return DiscountApplicationResult(
        applications=applications,
        total_discount=total,
        line_discounts=line_discounts,
    )


# ---------------------------------------------------------------------------
# Redemption confirmation (FR-6.8, §7)
# ---------------------------------------------------------------------------


def record_confirmed_redemptions(*, invoice, actor=None):
    """Increment per-customer usage counters for each applied discount on the invoice.

    Must be called within the same transaction.atomic() block as confirm_invoice.
    Idempotent: snapshots already confirmed are skipped without error.

    Args:
        invoice: The confirmed Invoice instance.
        actor: The User who confirmed (or None for system).
    """
    pending = list(
        InvoiceDiscountSnapshot.objects.select_for_update().filter(
            invoice=invoice, redemption_confirmed=False
        )
    )
    if not pending:
        return

    customer = invoice.customer

    for snapshot in pending:
        if snapshot.discount_id is None:
            logger.warning(
                "Discount snapshot %s has no linked discount (deleted); skipping redemption.",
                snapshot.pk,
            )
            snapshot.redemption_confirmed = True
            snapshot.save(update_fields=["redemption_confirmed"])
            continue

        redemption, _created = DiscountRedemption.objects.select_for_update().get_or_create(
            discount_id=snapshot.discount_id,
            customer=customer,
            defaults={"usage_count": 0},
        )

        discount = snapshot.discount
        if redemption.usage_count >= discount.usage_limit_per_customer:
            raise DiscountRedemptionConflict(
                f"Discount '{discount.name}' usage limit reached for this customer "
                f"({redemption.usage_count}/{discount.usage_limit_per_customer}). "
                "Cancel the invoice or contact Admin to resolve."
            )

        redemption.usage_count += 1
        redemption.save(update_fields=["usage_count", "updated_at"])

        snapshot.redemption_confirmed = True
        snapshot.save(update_fields=["redemption_confirmed"])

        record_audit(
            actor=actor,
            action="discount.redemption_confirmed",
            target=snapshot,
        )
        logger.info(
            "Discount %s redeemed for customer %s on invoice %s (usage now %s)",
            discount.pk,
            customer.pk,
            invoice.pk,
            redemption.usage_count,
        )
