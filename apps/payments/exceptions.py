class PaymentError(Exception):
    """Base for domain errors. The message is safe to show to the user."""


class InvoiceNotPayable(PaymentError):
    """Only a Confirmed invoice without a pending or successful payment can be paid."""


class PaymentAmountMismatch(PaymentError):
    """The amount must equal the invoice total exactly (BR-7, FR-7.4)."""


class DuplicatePayment(PaymentError):
    """The submission's idempotency key was already used for different details (FR-7.9)."""


class PaymentPending(PaymentError):
    """A gateway payment for the invoice is still waiting for confirmation."""


class InvalidPaymentDetails(PaymentError):
    """The method or payment date can't be accepted."""
