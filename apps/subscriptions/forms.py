from django import forms

from apps.accounts.models import Customer
from apps.catalog.models import PaymentTerm, Product, ProductVariant
from apps.plans.models import Plan

from .models import QuotationTemplate, QuotationTemplateLine
from .template_services import LINE_FIELDS, TEMPLATE_FIELDS

VARIANT_MISMATCH = "This variant does not belong to the selected product."


def _product_queryset():
    return Product.objects.available_for_new_lines().select_related("tax").order_by("name", "id")


def _variant_queryset():
    return ProductVariant.objects.select_related("product").order_by("product__name", "id")


def _variant_label(variant):
    return f"{variant.product.name} — {variant.dimension}: {variant.value}"


def _check_variant(cleaned):
    product, variant = cleaned.get("product"), cleaned.get("variant")
    if product and variant and variant.product_id != product.pk:
        raise forms.ValidationError({"variant": VARIANT_MISMATCH})


class TemplateForm(forms.ModelForm):
    """Only the declared fields are read; anything else submitted is ignored."""

    class Meta:
        model = QuotationTemplate
        fields = TEMPLATE_FIELDS
        labels = {"validity_days": "Validity (days)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = Plan.objects.order_by("name", "id")
        self.fields["plan"].empty_label = "Select a plan"


class TemplateLineForm(forms.ModelForm):
    class Meta:
        model = QuotationTemplateLine
        fields = LINE_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = _product_queryset()
        self.fields["variant"].queryset = _variant_queryset()
        self.fields["variant"].label_from_instance = _variant_label
        self.fields["variant"].empty_label = "No variant"

    def clean(self):
        cleaned = super().clean()
        _check_variant(cleaned)
        return cleaned


class BaseTemplateLineFormSet(forms.BaseInlineFormSet):
    def line_rows(self):
        """Validated lines to keep, as plain dicts for the service. The submitted
        id is passed on as-is so a foreign id is rejected there, not saved as new."""
        rows = []
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            submitted = data.get("id")
            rows.append(
                {
                    "id": submitted.pk if submitted else None,
                    **{name: data.get(name) for name in LINE_FIELDS},
                }
            )
        return rows


TemplateLineFormSet = forms.inlineformset_factory(
    QuotationTemplate,
    QuotationTemplateLine,
    form=TemplateLineForm,
    formset=BaseTemplateLineFormSet,
    extra=1,
    can_delete=True,
)


class SubscriptionCreateForm(forms.Form):
    """Customer, optional template, dates and payment terms. Status, number and
    prices are never accepted from the browser."""

    customer = forms.ModelChoiceField(
        Customer.objects.none(), empty_label="Select a customer"
    )
    template = forms.ModelChoiceField(
        QuotationTemplate.objects.none(),
        required=False,
        empty_label="Start blank",
        label="Quotation template",
        help_text="Copies the template's plan and lines. They stay editable afterwards.",
    )
    plan = forms.ModelChoiceField(
        Plan.objects.none(),
        required=False,
        empty_label="Select a plan",
        help_text="Used when starting blank. Ignored when a template is chosen.",
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    payment_terms = forms.ModelChoiceField(
        PaymentTerm.objects.none(), empty_label="Select payment terms"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.select_related("user").order_by(
            "user__email"
        )
        self.fields["template"].queryset = QuotationTemplate.objects.order_by("name", "id")
        self.fields["plan"].queryset = Plan.objects.order_by("name", "id")
        self.fields["payment_terms"].queryset = PaymentTerm.objects.order_by("name", "id")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("template") and not cleaned.get("plan") and "plan" not in self.errors:
            self.add_error("plan", "Choose a plan, or choose a quotation template.")
        start, expiry = cleaned.get("start_date"), cleaned.get("expiry_date")
        if start and expiry and expiry < start:
            self.add_error("expiry_date", "The expiry date can't be earlier than the start date.")
        return cleaned


class SubscriptionLineForm(forms.Form):
    """Product, optional variant, quantity. Price and tax are always recalculated
    on the server from the catalog."""

    product = forms.ModelChoiceField(Product.objects.none(), empty_label="Select a product")
    variant = forms.ModelChoiceField(
        ProductVariant.objects.none(), required=False, empty_label="No variant"
    )
    quantity = forms.IntegerField(min_value=1, initial=1)
    is_addon = forms.BooleanField(required=False, label="This line is an add-on")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = _product_queryset()
        self.fields["variant"].queryset = _variant_queryset()
        self.fields["variant"].label_from_instance = _variant_label

    def clean(self):
        cleaned = super().clean()
        _check_variant(cleaned)
        return cleaned
