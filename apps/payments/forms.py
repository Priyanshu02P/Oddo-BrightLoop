import uuid
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.billing.models import Invoice

from . import selectors
from .models import Payment
from .providers import SimulatedOutcome


class InvoiceChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, invoice):
        return (
            f"{invoice.number} · {invoice.customer_email} · {invoice.total:,.2f} "
            f"· due {invoice.due_date:%Y-%m-%d}"
        )


class PaymentForm(forms.Form):
    """Record-payment form (FR-7.1). Only the declared fields are read, so a
    submitted status, provider result or customer is ignored. The amount is
    checked against the stored invoice total by the service, not here."""

    invoice = InvoiceChoiceField(Invoice.objects.none(), empty_label="Select an invoice")
    method = forms.ChoiceField(label="Payment method")
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    payment_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    note = forms.CharField(
        required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 2})
    )
    simulated_outcome = forms.ChoiceField(
        label="Simulated gateway outcome (test mode)",
        required=False,
        choices=[("", "Select an outcome"), *SimulatedOutcome.choices],
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=64)

    def __init__(self, *args, mock_gateway, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("idempotency_key", uuid.uuid4().hex)
        kwargs["initial"].setdefault("payment_date", timezone.localdate())
        super().__init__(*args, **kwargs)
        payable = selectors.payable_invoices()
        if self.is_bound and self.data.get("invoice", "").isdigit():
            # Keep the submitted invoice selectable so the service can explain
            # why it is not payable (paid meanwhile, cancelled, ...).
            payable = Invoice.objects.filter(
                Q(pk__in=payable.values("pk")) | Q(pk=int(self.data["invoice"]))
            ).order_by("due_date", "id")
        self.fields["invoice"].queryset = payable
        methods = Payment.Method.choices
        if not mock_gateway:
            methods = [c for c in methods if c[0] != Payment.Method.TEST_GATEWAY]
            del self.fields["simulated_outcome"]
        self.fields["method"].choices = [("", "Select a method"), *methods]

    def clean_payment_date(self):
        payment_date = self.cleaned_data["payment_date"]
        if payment_date > timezone.localdate():
            raise forms.ValidationError("The payment date can't be in the future.")
        return payment_date

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("method") == Payment.Method.TEST_GATEWAY and not cleaned.get(
            "simulated_outcome"
        ):
            self.add_error("simulated_outcome", "Choose what the test gateway should do.")
        return cleaned
