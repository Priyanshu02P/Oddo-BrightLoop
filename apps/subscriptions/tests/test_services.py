from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.models import AuditLog
from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory
from apps.plans.exceptions import PlanNotAvailable
from apps.plans.tests.factories import PlanFactory
from apps.subscriptions import notifications, services
from apps.subscriptions.exceptions import (
    ActionNotAllowedByPlan,
    EmptyQuotation,
    InvalidLine,
    InvalidSubscriptionTransition,
    QuotationExpired,
    SubscriptionNotEditable,
)
from apps.subscriptions.models import Subscription

from .factories import (
    PaymentTermFactory,
    QuotationTemplateFactory,
    QuotationTemplateLineFactory,
    SubscriptionFactory,
    SubscriptionLineFactory,
)

pytestmark = pytest.mark.django_db

Status = Subscription.Status
FUTURE = date(2999, 1, 1)
PAST = date(2000, 1, 1)


def create(actor, customer, **overrides):
    args = {
        "actor": actor,
        "customer": customer,
        "plan": PlanFactory(),
        "payment_terms": PaymentTermFactory(),
        "start_date": date(2026, 6, 1),
        "expiry_date": date(2026, 12, 31),
    }
    args.update(overrides)
    return services.create_subscription(**args)


def with_line(subscription):
    SubscriptionLineFactory(subscription=subscription)
    return subscription


# --- Creation and numbering --------------------------------------------------


def test_blank_subscription_is_a_priced_draft(staff_user, customer):
    product = ProductFactory(sales_price=Decimal("100.00"))
    variant = ProductVariantFactory(product=product, price_adjustment=Decimal("10.00"))
    subscription = create(
        staff_user,
        customer,
        lines=[{"product": product, "variant": variant, "quantity": 2, "is_addon": True}],
    )
    line = subscription.lines.get()
    assert subscription.status == Status.DRAFT
    assert subscription.quotation_validity_days == 30
    assert (line.unit_price, line.amount, line.is_addon) == (
        Decimal("110.00"),
        Decimal("220.00"),
        True,
    )
    assert AuditLog.objects.filter(action="subscription.created").count() == 1


def test_numbers_are_sequential_and_never_reused(admin_user, customer):
    first = create(admin_user, customer)
    second = create(admin_user, customer)
    first.delete()
    third = create(admin_user, customer)
    assert [first.number, second.number, third.number] == [
        "SUB-000001",
        "SUB-000002",
        "SUB-000003",
    ]


def test_failed_creation_leaves_nothing_behind(admin_user, customer):
    archived = ProductFactory(is_archived=True)
    with pytest.raises(InvalidLine):
        create(admin_user, customer, lines=[{"product": archived, "quantity": 1}])
    assert Subscription.objects.count() == 0


def test_template_lines_are_copied_and_stay_independent(staff_user, customer):
    template = QuotationTemplateFactory(validity_days=7)
    template_line = QuotationTemplateLineFactory(template=template, quantity=2)
    subscription = create(staff_user, customer, template=template, plan=PlanFactory())
    assert subscription.plan == template.plan
    assert subscription.quotation_validity_days == 7
    assert subscription.lines.get().quantity == 2

    template_line.quantity = 9
    template_line.save()
    template.validity_days = 99
    template.save()
    subscription.refresh_from_db()
    assert subscription.lines.get().quantity == 2
    assert subscription.quotation_validity_days == 7


def test_customer_cannot_create_subscriptions(customer_user, customer):
    with pytest.raises(PermissionDenied):
        create(customer_user, customer)


def test_plan_outside_its_availability_window_is_rejected(staff_user, customer):
    plan = PlanFactory(availability_end_date=date(2026, 3, 1))
    with pytest.raises(PlanNotAvailable):
        create(staff_user, customer, plan=plan)
    assert Subscription.objects.count() == 0


# --- Draft lines ---------------------------------------------------------------


def test_lines_change_only_while_draft(staff_user, customer):
    subscription = with_line(create(staff_user, customer))
    row = {"product": ProductFactory(), "variant": None, "quantity": 3, "is_addon": False}
    services.add_line(actor=staff_user, subscription=subscription, row=row)
    assert subscription.lines.count() == 2
    services.send_quotation(actor=staff_user, subscription=subscription)
    with pytest.raises(SubscriptionNotEditable):
        services.add_line(actor=staff_user, subscription=subscription, row=row)
    with pytest.raises(SubscriptionNotEditable):
        services.remove_line(actor=staff_user, line=subscription.lines.first())


def test_update_line_reprices_from_the_catalog(staff_user, customer):
    subscription = create(staff_user, customer)
    product = ProductFactory(sales_price=Decimal("50.00"))
    line = services.add_line(
        actor=staff_user,
        subscription=subscription,
        row={"product": product, "variant": None, "quantity": 1},
    )
    product.sales_price = Decimal("80.00")
    product.save()
    line = services.update_line(
        actor=staff_user, line=line, row={"product": product, "variant": None, "quantity": 2}
    )
    assert (line.unit_price, line.amount) == (Decimal("80.00"), Decimal("160.00"))


# --- Quotation lifecycle -------------------------------------------------------


def test_send_quotation_sets_deadline_and_emails(staff_user, customer, sent_quotations):
    subscription = with_line(create(staff_user, customer))
    sent = services.send_quotation(actor=staff_user, subscription=subscription)
    assert sent.status == Status.QUOTATION
    assert sent.valid_until == timezone.localdate() + timedelta(days=30)
    assert [s.pk for s in sent_quotations] == [sent.pk]
    audit = AuditLog.objects.get(action="subscription.status_changed")
    assert (audit.actor, audit.from_status, audit.to_status) == (staff_user, "draft", "quotation")


def test_quotation_needs_a_line(staff_user, customer):
    subscription = create(staff_user, customer)
    with pytest.raises(EmptyQuotation):
        services.send_quotation(actor=staff_user, subscription=subscription)
    subscription.refresh_from_db()
    assert subscription.status == Status.DRAFT


def test_email_failure_does_not_undo_the_quotation(staff_user, customer, monkeypatch):
    def broken(subscription):
        raise OSError("smtp down")

    monkeypatch.setattr(notifications, "send_quotation_email", broken)
    subscription = with_line(create(staff_user, customer))
    services.send_quotation(actor=staff_user, subscription=subscription)
    subscription.refresh_from_db()
    assert subscription.status == Status.QUOTATION


def test_customer_cannot_send_quotations(customer_user, customer):
    subscription = with_line(SubscriptionFactory(customer=customer))
    with pytest.raises(PermissionDenied):
        services.send_quotation(actor=customer_user, subscription=subscription)


def quotation(customer, valid_until=FUTURE, **overrides):
    return SubscriptionFactory(
        customer=customer, status=Status.QUOTATION, valid_until=valid_until, **overrides
    )


def test_customer_accepts_their_own_valid_quotation(customer_user, customer):
    accepted = services.accept_quotation(actor=customer_user, subscription=quotation(customer))
    assert accepted.status == Status.CONFIRMED


def test_staff_can_accept_on_behalf(staff_user, customer):
    accepted = services.accept_quotation(actor=staff_user, subscription=quotation(customer))
    assert accepted.status == Status.CONFIRMED


def test_customer_cannot_accept_someone_elses_quotation(customer_user, other_customer):
    subscription = quotation(other_customer)
    with pytest.raises(PermissionDenied):
        services.accept_quotation(actor=customer_user, subscription=subscription)
    subscription.refresh_from_db()
    assert subscription.status == Status.QUOTATION


def test_expired_quotation_cannot_be_accepted(customer_user, customer):
    subscription = quotation(customer, valid_until=PAST)
    with pytest.raises(QuotationExpired):
        services.accept_quotation(actor=customer_user, subscription=subscription)
    subscription.refresh_from_db()
    assert subscription.status == Status.QUOTATION


def test_quotation_is_still_acceptable_on_its_last_day(customer_user, customer):
    subscription = quotation(customer, valid_until=timezone.localdate())
    assert services.accept_quotation(actor=customer_user, subscription=subscription).status == (
        Status.CONFIRMED
    )


def test_only_a_quotation_can_be_accepted(customer_user, customer):
    subscription = SubscriptionFactory(customer=customer, status=Status.ACTIVE)
    with pytest.raises(InvalidSubscriptionTransition):
        services.accept_quotation(actor=customer_user, subscription=subscription)


# --- Plan-governed actions -----------------------------------------------------


def active(customer, **plan_options):
    return SubscriptionFactory(
        customer=customer, status=Status.ACTIVE, plan=PlanFactory(**plan_options)
    )


def test_pause_requires_the_plan_option(customer_user, customer):
    subscription = active(customer, allow_pause=False)
    with pytest.raises(ActionNotAllowedByPlan):
        services.pause_subscription(actor=customer_user, subscription=subscription)
    subscription.refresh_from_db()
    assert subscription.status == Status.ACTIVE


def test_customer_pauses_and_resumes_with_a_recalculated_billing_date(customer_user, customer):
    subscription = active(customer, allow_pause=True)
    paused = services.pause_subscription(actor=customer_user, subscription=subscription)
    assert paused.status == Status.PAUSED
    resumed = services.resume_subscription(actor=customer_user, subscription=paused)
    assert resumed.status == Status.ACTIVE
    assert resumed.next_billing_date == timezone.localdate()


def test_staff_obey_the_plan_option_too(staff_user, customer):
    with pytest.raises(ActionNotAllowedByPlan):
        services.pause_subscription(
            actor=staff_user, subscription=active(customer, allow_pause=False)
        )


def test_customer_cannot_pause_someone_elses_subscription(customer_user, other_customer):
    subscription = active(other_customer, allow_pause=True)
    with pytest.raises(PermissionDenied):
        services.pause_subscription(actor=customer_user, subscription=subscription)


def test_cancel_closes_when_plan_allows_and_closed_is_terminal(customer_user, customer):
    subscription = active(customer, allow_close_early=True)
    closed = services.cancel_subscription(actor=customer_user, subscription=subscription)
    assert (closed.status, closed.closed_reason) == (Status.CLOSED, "cancelled")
    with pytest.raises(InvalidSubscriptionTransition):
        services.resume_subscription(actor=customer_user, subscription=closed)


def test_cancel_denied_when_plan_disallows(customer_user, customer):
    with pytest.raises(ActionNotAllowedByPlan):
        services.cancel_subscription(
            actor=customer_user, subscription=active(customer, allow_close_early=False)
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (Status.DRAFT, Status.ACTIVE),
        (Status.DRAFT, Status.CONFIRMED),
        (Status.QUOTATION, Status.ACTIVE),
        (Status.CONFIRMED, Status.PAUSED),
        (Status.ACTIVE, Status.QUOTATION),
        (Status.CLOSED, Status.ACTIVE),
    ],
)
def test_invalid_transitions_are_rejected_and_not_audited(current, target):
    subscription = SubscriptionFactory(status=current)
    with pytest.raises(InvalidSubscriptionTransition):
        services.transition_subscription(subscription, target)
    subscription.refresh_from_db()
    assert subscription.status == current
    assert not AuditLog.objects.exists()
