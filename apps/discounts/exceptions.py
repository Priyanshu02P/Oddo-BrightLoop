"""Domain exceptions for M6 Discounts (CODING_STANDARDS.md §7.1)."""


class DiscountError(Exception):
    """Base for discount domain errors. The message is safe to show to the user."""


class InvalidDiscountRule(DiscountError):
    """The discount rule data fails validation."""


class DiscountNotApplicable(DiscountError):
    """The discount cannot be applied in this context."""


class DiscountUsageLimitReached(DiscountError):
    """The customer has used this discount the maximum allowed times."""


class DiscountRedemptionConflict(DiscountError):
    """Concurrent confirmation attempted to redeem the same discount twice."""
