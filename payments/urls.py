from django.urls import path
from . import views as v

urlpatterns = [
    path("payments/", v.payment_list, name="payment_list"),
    path("invoices/<int:pk>/payments/new/", v.payment_new, name="payment_new"),
]
