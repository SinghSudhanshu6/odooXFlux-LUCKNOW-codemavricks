from django import forms
from accounts.forms import StyledModelForm, date_widget
from .models import Plan, Product, ProductVariant, QuotationTemplate, TemplateLine


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["name", "product_type", "sales_price", "cost_price", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class VariantForm(StyledModelForm):
    class Meta:
        model = ProductVariant
        fields = ["attribute", "value", "extra_price"]


class PlanForm(StyledModelForm):
    class Meta:
        model = Plan
        fields = ["name", "price", "billing_period", "min_qty", "start_date", "end_date",
                  "auto_close", "closable", "pausable", "renewable"]
        widgets = {"start_date": date_widget(), "end_date": date_widget()}


class TemplateForm(StyledModelForm):
    class Meta:
        model = QuotationTemplate
        fields = ["name", "plan", "validity_days"]


class TemplateLineForm(StyledModelForm):
    class Meta:
        model = TemplateLine
        fields = ["product", "variant", "quantity"]

    def clean(self):
        d = super().clean()
        if d.get("variant") and d.get("product") and d["variant"].product_id != d["product"].pk:
            self.add_error("variant", "This variant belongs to a different product.")
        return d
