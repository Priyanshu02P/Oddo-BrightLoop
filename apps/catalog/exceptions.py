class StaleVariantData(Exception):
    """A submitted variant no longer belongs to the product (changed by another request)."""
