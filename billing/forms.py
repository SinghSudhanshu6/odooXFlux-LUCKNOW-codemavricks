from django import forms
from accounts.forms import StyledModelForm, date_widget
from .models import Discount, Tax


class TaxForm(StyledModelForm):
    class Meta:
        model = Tax
        fields = ["name", "rate_percent", "active"]


class DiscountForm(StyledModelForm):
    class Meta:
        model = Discount
        fields = ["name", "kind", "value", "min_purchase", "min_qty", "start_date", "end_date",
                  "usage_limit", "products", "active"]
        widgets = {"start_date": date_widget(), "end_date": date_widget(),
                   "products": forms.SelectMultiple(attrs={"size": 5})}
