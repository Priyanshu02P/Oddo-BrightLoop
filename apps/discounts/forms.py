"""Admin-only forms for creating and editing discount rules (FR-6.1 – FR-6.4)."""

from decimal import Decimal

from django import forms

from apps.catalog.models import Product

from .models import Discount


class DiscountForm(forms.ModelForm):
    """Create / edit form for a Discount rule.

    The 'products' field is only required when scope_type == SELECTED_PRODUCTS.
    JavaScript on the page shows/hides the products field based on scope selection.
    """

    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.filter(is_archived=False).order_by("name", "id"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Products",
        help_text="Required when scope is 'Selected products'.",
    )

    class Meta:
        model = Discount
        fields = [
            "name",
            "discount_type",
            "value",
            "minimum_purchase_amount",
            "minimum_quantity",
            "start_date",
            "end_date",
            "usage_limit_per_customer",
            "scope_type",
            "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        # Pre-populate the products field from existing DiscountProduct links.
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if instance and instance.pk:
            self.fields["products"].initial = list(
                instance.discount_products.values_list("product_id", flat=True)
            )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def clean_value(self):
        value = self.cleaned_data.get("value")
        if value is not None and value <= Decimal("0"):
            raise forms.ValidationError("The discount value must be greater than zero.")
        return value

    def clean_usage_limit_per_customer(self):
        limit = self.cleaned_data.get("usage_limit_per_customer")
        if limit is not None and limit < 1:
            raise forms.ValidationError("The usage limit per customer must be at least 1.")
        return limit

    def clean(self):
        cleaned = super().clean()
        discount_type = cleaned.get("discount_type")
        value = cleaned.get("value")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        scope_type = cleaned.get("scope_type")
        products = cleaned.get("products")

        # Percentage cap (per spec: percentage value must be 0 < v <= 100).
        if discount_type == Discount.DiscountType.PERCENTAGE and value is not None:
            if value > Decimal("100"):
                self.add_error(
                    "value",
                    "Percentage discount value cannot exceed 100%.",
                )

        # Date ordering.
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")

        # Products required for SELECTED_PRODUCTS scope.
        if scope_type == Discount.ScopeType.SELECTED_PRODUCTS:
            if not products:
                self.add_error(
                    "products",
                    "At least one product must be selected for a 'Selected products' discount.",
                )
        else:
            # WHOLE_SUBSCRIPTION: clear any submitted products so the service
            # doesn't accidentally save them.
            cleaned["products"] = []

        return cleaned
