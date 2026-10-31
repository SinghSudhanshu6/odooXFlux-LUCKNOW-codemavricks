from django.urls import path
from . import views as v

urlpatterns = [
    path("portal/subscriptions/", v.subscriptions, name="portal_subscriptions"),
    path("portal/subscriptions/<int:pk>/", v.subscription, name="portal_subscription"),
    path("portal/subscriptions/<int:pk>/<str:action>/", v.subscription_action, name="portal_subscription_action"),
    path("portal/invoices/", v.invoices, name="portal_invoices"),
    path("portal/invoices/<int:pk>/", v.invoice, name="portal_invoice"),
    path("portal/invoices/<int:pk>/pay/", v.pay, name="portal_pay"),
    path("portal/profile/", v.profile, name="portal_profile"),
]
