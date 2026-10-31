"""PaymentProvider boundary (FR-7.7, NFR-9).

A provider collects (or acknowledges) a payment and reports a normalised
outcome. It never touches invoice status or the database; the payment service
does that. Both implementations here run locally and inside the service's
transaction. A real gateway would make an external call that a rollback can't
undo, and needs a reconciliation design before it is added (M7 open decision 9).
"""

from dataclasses import dataclass
from typing import Protocol

from django.db import models

from .models import Payment

Outcome = Payment.Status


class SimulatedOutcome(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure (declined)"
    DELAY = "delay", "Delay (pending)"


@dataclass(frozen=True)
class ProviderResult:
    outcome: str  # a Payment.Status value
    provider_reference: str = ""
    failure_reason: str = ""


class PaymentProvider(Protocol):
    test_mode: bool

    def collect(self, *, payment_reference, invoice, amount) -> ProviderResult: ...


class ManualProvider:
    """Money already received outside the system; Staff record it (FR-7.1)."""

    test_mode = False

    def collect(self, *, payment_reference, invoice, amount):
        return ProviderResult(Outcome.SUCCEEDED)


class MockGatewayProvider:
    """Deterministic fake gateway for development and tests (FR-7.7)."""

    test_mode = True

    def __init__(self, simulated_outcome):
        self.simulated_outcome = simulated_outcome

    def collect(self, *, payment_reference, invoice, amount):
        reference = f"TEST-{payment_reference}"
        if self.simulated_outcome == SimulatedOutcome.SUCCESS:
            return ProviderResult(Outcome.SUCCEEDED, reference)
        if self.simulated_outcome == SimulatedOutcome.DELAY:
            return ProviderResult(Outcome.PENDING, reference)
        return ProviderResult(
            Outcome.FAILED, reference, "The test gateway declined the payment (simulated)."
        )


def provider_for(method, simulated_outcome=None):
    if method == Payment.Method.TEST_GATEWAY:
        return MockGatewayProvider(simulated_outcome)
    return ManualProvider()
