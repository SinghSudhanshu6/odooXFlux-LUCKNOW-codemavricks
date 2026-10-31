from django.urls import path
from . import views as v

urlpatterns = [
    path("invoices/", v.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", v.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/pdf/", v.invoice_pdf, name="invoice_pdf"),
    path("invoices/<int:pk>/<str:action>/", v.invoice_action, name="invoice_action"),
    path("billing/run/", v.billing_run, name="billing_run"),
    path("taxes/", v.tax_list, name="tax_list"),
    path("taxes/new/", v.tax_create, name="tax_create"),
    path("taxes/<int:pk>/edit/", v.tax_edit, name="tax_edit"),
    path("discounts/", v.discount_list, name="discount_list"),
    path("discounts/new/", v.discount_create, name="discount_create"),
    path("discounts/<int:pk>/edit/", v.discount_edit, name="discount_edit"),
]
