"""Invoice actions offered on the internal screens (FR-5.5).

The table drives the confirmation page and the buttons only. Whether an action
is really allowed is decided by the service it calls.
"""

from dataclasses import dataclass

from . import services
from .models import Invoice

Status = Invoice.Status


@dataclass(frozen=True)
class Action:
    label: str
    service: object
    explanation: str
    success: str
    danger: bool = False


ACTIONS = {
    "confirm": Action(
        "Confirm invoice",
        services.confirm_invoice,
        "Its amounts become final and can't be edited afterwards. Mistakes are corrected by "
        "cancelling it.",
        "Invoice confirmed.",
    ),
    "send": Action(
        "Send by email",
        services.send_invoice,
        "The invoice details are emailed to the customer's address on the invoice.",
        "Invoice emailed to the customer.",
    ),
    "cancel": Action(
        "Cancel invoice",
        services.cancel_invoice,
        "Cancelling can't be undone. This billing period stays billed: the subscription is not "
        "invoiced again for it, and no replacement invoice is created.",
        "Invoice cancelled.",
        danger=True,
    ),
}


def available_actions(invoice):
    """Keys of the buttons worth showing for this status (UI only)."""
    keys = []
    if invoice.status == Status.DRAFT:
        keys.append("confirm")
    if invoice.status in (Status.CONFIRMED, Status.PAID):
        keys.append("send")
    if invoice.status in (Status.DRAFT, Status.CONFIRMED):
        keys.append("cancel")
    return [(key, ACTIONS[key]) for key in keys]
