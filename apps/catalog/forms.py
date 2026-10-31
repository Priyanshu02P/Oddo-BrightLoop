from django import forms

from .models import PaymentTerm, Product, ProductVariant, Tax
from .services import PRODUCT_FIELDS, VARIANT_FIELDS


class ProductForm(forms.ModelForm):
    """Only the declared fields are read, so a submitted is_archived (or any
    computed price) is ignored."""

    class Meta:
        model = Product
        fields = PRODUCT_FIELDS
        labels = {
            "sales_price": "Sales price (base, before tax)",
            "tax": "Associated tax",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tax"].queryset = Tax.objects.order_by("name", "id")
        self.fields["tax"].empty_label = "Select a tax"


class BaseVariantFormSet(forms.BaseInlineFormSet):
    def variant_rows(self):
        """Validated variant values to keep, as plain dicts for the services.

        The submitted id is passed on as-is, so an id that is not (or no longer)
        one of this product's variants is rejected by the service instead of
        being silently saved as a new value.
        """
        rows = []
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            submitted = data.get("id")
            rows.append(
                {
                    "id": submitted.pk if submitted else None,
                    **{name: data[name] for name in VARIANT_FIELDS},
                }
            )
        return rows


VariantFormSet = forms.inlineformset_factory(
    Product,
    ProductVariant,
    formset=BaseVariantFormSet,
    fields=VARIANT_FIELDS,
    labels={"price_adjustment": "Price adjustment"},
    extra=1,
    can_delete=True,
)


class TaxForm(forms.ModelForm):
    class Meta:
        model = Tax
        fields = ("name", "rate")
        labels = {"rate": "Tax rate (%)"}
        help_texts = {"rate": "Enter the percentage value, e.g. 18 for 18%."}


class PaymentTermForm(forms.ModelForm):
    class Meta:
        model = PaymentTerm
        fields = ("name", "days")
        labels = {"days": "Due-date rule / number of days"}
        help_texts = {
            "days": "0 means due immediately; 30 means due 30 calendar days after the invoice date."
        }
