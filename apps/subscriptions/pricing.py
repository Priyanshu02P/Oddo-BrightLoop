"""Server-side line pricing (FR-4.4, BR-8, BR-13, NFR-10).

Prices are tax-exclusive. Tax comes only from the product's tax. Money is
rounded per line, two decimals, half-up (working assumption J).
"""

from decimal import ROUND_HALF_UP, Decimal

from .exceptions import InvalidLine

CENT = Decimal("0.01")


def round_money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def price_line(*, product, variant, quantity):
    """Return the stored commercial values of one line, calculated from the catalog.

    Nothing here is read from the browser: price and tax come from the product
    (plus the variant's adjustment), so a forged value can never reach a line.
    """
    if quantity is None or quantity < 1:
        raise InvalidLine("The quantity must be at least 1.")
    if product.is_archived:
        raise InvalidLine(f"“{product.name}” is archived and can't be added to new lines.")
    if variant is not None and variant.product_id != product.pk:
        raise InvalidLine("The selected variant does not belong to the selected product.")
    unit_price = product.sales_price + (variant.price_adjustment if variant else Decimal("0"))
    tax_rate = product.tax.rate
    amount = round_money(unit_price * quantity)
    return {
        "unit_price": round_money(unit_price),
        "tax_rate": tax_rate,
        "amount": amount,
        "tax_amount": round_money(amount * tax_rate / Decimal("100")),
    }
