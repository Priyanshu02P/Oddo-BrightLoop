class BillingError(Exception):
    """Base for domain errors. The message is safe to show to the user."""


class SkipSubscription(BillingError):
    """The subscription is not billed in this run (not due, paused, already invoiced)."""


class InvalidInvoiceTransition(BillingError):
    """The requested status change is not allowed from the current status."""


class InvoiceLocked(BillingError):
    """A confirmed, paid or cancelled invoice's financial values can't change (FR-5.10)."""


class InvoiceNotSendable(BillingError):
    """Only issued invoices can be emailed to the customer."""
