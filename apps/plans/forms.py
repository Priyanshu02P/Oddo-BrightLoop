from django import forms

from .models import Plan
from .services import PLAN_FIELDS


class PlanForm(forms.ModelForm):
    """Only the declared fields are read, so any other submitted value is ignored."""

    class Meta:
        model = Plan
        fields = PLAN_FIELDS
        labels = {
            "price": "Price (before tax)",
            "minimum_quantity": "Minimum quantity",
            "availability_start_date": "Availability start date",
            "availability_end_date": "Availability end date",
            "auto_close_at_end_date": "Auto-close at end date",
            "allow_close_early": "Close early",
            "allow_pause": "Pause",
            "allow_renew": "Renew",
        }
        widgets = {
            "availability_start_date": forms.DateInput(attrs={"type": "date"}),
            "availability_end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["billing_period"].choices = [("", "Select a billing period")] + list(
            Plan.BillingPeriod.choices
        )
        self.fields["renewal_mode"].choices = [("", "Select a renewal mode")] + list(
            Plan.RenewalMode.choices
        )
