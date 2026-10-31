from django.urls import path
from . import views as v

urlpatterns = [
    path("subscriptions/", v.subscription_list, name="subscription_list"),
    path("subscriptions/new/", v.subscription_create, name="subscription_create"),
    path("subscriptions/from-template/<int:template_id>/", v.from_template, name="from_template"),
    path("subscriptions/<int:pk>/", v.subscription_detail, name="subscription_detail"),
    path("subscriptions/<int:pk>/edit/", v.subscription_edit, name="subscription_edit"),
    path("subscriptions/<int:pk>/<str:action>/", v.subscription_action, name="subscription_action"),
]
