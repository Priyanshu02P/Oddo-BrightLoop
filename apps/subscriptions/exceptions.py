class SubscriptionError(Exception):
    """Base for domain errors. The message is safe to show to the user."""


class InvalidSubscriptionTransition(SubscriptionError):
    """The requested status change is not allowed from the current status."""


class QuotationExpired(SubscriptionError):
    """The quotation's validity period has ended (BR-11)."""


class QuotationNotExpired(SubscriptionError):
    """The quotation is still valid, so the expiry job must leave it alone."""


class ActionNotAllowedByPlan(SubscriptionError):
    """The plan's lifecycle options do not enable this action (BR-12)."""


class SubscriptionNotEditable(SubscriptionError):
    """Lines can only be changed while the subscription is a Draft."""


class EmptyQuotation(SubscriptionError):
    """A quotation needs at least one line before it can be sent."""


class InvalidLine(SubscriptionError):
    """The product, variant or quantity of a line is not acceptable."""


class StaleTemplateLines(SubscriptionError):
    """A submitted template line no longer belongs to the template."""
