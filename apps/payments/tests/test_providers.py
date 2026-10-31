import pytest

from apps.payments.models import Payment
from apps.payments.providers import (
    ManualProvider,
    MockGatewayProvider,
    SimulatedOutcome,
    provider_for,
)

Outcome = Payment.Status


def collect(provider):
    return provider.collect(payment_reference="PAY-000001", invoice=None, amount=None)


@pytest.mark.parametrize(
    "simulated, outcome",
    [
        (SimulatedOutcome.SUCCESS, Outcome.SUCCEEDED),
        (SimulatedOutcome.FAILURE, Outcome.FAILED),
        (SimulatedOutcome.DELAY, Outcome.PENDING),
    ],
)
def test_mock_gateway_returns_a_normalised_outcome(simulated, outcome):
    result = collect(MockGatewayProvider(simulated))
    assert result.outcome == outcome
    assert result.provider_reference == "TEST-PAY-000001"  # visibly a test transaction


def test_mock_failure_explains_itself_as_simulated():
    assert "simulated" in collect(MockGatewayProvider(SimulatedOutcome.FAILURE)).failure_reason


def test_manual_methods_acknowledge_money_already_received():
    result = collect(ManualProvider())
    assert (result.outcome, result.provider_reference) == (Outcome.SUCCEEDED, "")
    assert ManualProvider.test_mode is False and MockGatewayProvider.test_mode is True


def test_the_method_picks_the_provider():
    assert isinstance(provider_for(Payment.Method.CASH), ManualProvider)
    assert isinstance(provider_for(Payment.Method.TEST_GATEWAY, "success"), MockGatewayProvider)
