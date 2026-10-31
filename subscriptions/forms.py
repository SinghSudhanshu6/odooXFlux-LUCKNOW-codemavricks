from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from accounts.forms import StyledForm, StyledModelForm, date_widget
from accounts.models import Customer
from billing.models import Tax
from .models import Subscription, SubscriptionLine


class SubscriptionForm(StyledModelForm):
    class Meta:
        model = Subscription
        fields = ["customer", "plan", "start_date", "expiry_date", "payment_terms", "notes"]
        widgets = {"start_date": date_widget(), "expiry_date": date_widget(),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        d = super().clean()
        if d.get("start_date") and d.get("expiry_date") and d["expiry_date"] <= d["start_date"]:
            self.add_error("expiry_date", "Expiry must be after the start date.")
        return d


class LineForm(StyledModelForm):
    class Meta:
        model = SubscriptionLine
        fields = ["product", "variant", "quantity", "unit_price", "tax", "discount"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["tax"].queryset = Tax.objects.filter(active=True)
        self.fields["variant"].label_from_instance = lambda v: f"{v.product.name}: {v.value} (+{v.extra_price})"

    def clean(self):
        d = super().clean()
        if d.get("variant") and d.get("product") and d["variant"].product_id != d["product"].pk:
            self.add_error("variant", "This variant belongs to a different product.")
        return d


class BaseLineFormSet(BaseInlineFormSet):
    plan = None

    def clean(self):
        super().clean()
        live = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if not live:
            raise forms.ValidationError("Add at least one product line.")
        if self.plan:
            for f in live:
                if f.cleaned_data["quantity"] < self.plan.min_qty:
                    f.add_error("quantity", f"This plan needs a quantity of at least {self.plan.min_qty}.")


LineFormSet = inlineformset_factory(Subscription, SubscriptionLine, form=LineForm,
                                    formset=BaseLineFormSet, extra=3, can_delete=True)


class FromTemplateForm(StyledForm):
    customer = forms.ModelChoiceField(Customer.objects.all())
    start_date = forms.DateField(widget=date_widget())
